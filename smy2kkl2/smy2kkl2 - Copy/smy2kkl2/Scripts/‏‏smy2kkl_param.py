#
# Convert smy data to  kkl standard
#
#-------------------------------------------------------------------------------
# Name:       smy2kkl_param.py
# Purpose:    Convert smy data to  kkl standard
#             
# Author:      Michael Denisyuk
#
# Created:     04-11-2023
# Last Update: 21-11-2023 
#-------------------------------------------------------------------------------

import sys
import os
import zipfile
import arcpy
import pandas as pd
import numpy as np

import smy_functions as fn


def convert_data(out_gdb, in_tab, domains_df, tab_design_df, converted_csv):

    try:
        ############################################################
        # Create lists and dictionaries to manage converting process
        ############################################################
        
        desc = arcpy.da.Describe(in_tab)
        
        all_fields = [f.name for f in arcpy.ListFields(in_tab)]    
        rqd_fields = [f.name for f in arcpy.ListFields(in_tab) if f.required]

        if in_tab == 'Samples':
            exclided_fields = rqd_fields + ['SiteID', 'Date', 'stand_ID']
        elif in_tab == 'Stands':
            exclided_fields = rqd_fields + ['Date']
        elif in_tab.split('_')[0].lower() == 'samples':
            exclided_fields = rqd_fields + ['parentglobalid']
        elif in_tab.split('_')[0].lower() == 'stands':
            exclided_fields = rqd_fields + ['stand_ID']

        # Create list of fields that will be deleted from origin layer or table.
        fields_to_delete = [ f for f in all_fields if not f in exclided_fields]
        
        
        src_out_names ={}       # Will used to rename column names 
        src_flds_dic = {}       # Will used to convert fields values
        fields_to_add = []      # Will used to add 'kkl' fields to a standalone table

        #arcpy.AddMessage('Creating lists and dictionaries to manage converting process')
        for row in tab_design_df.itertuples(False):
            if desc['dataType'] == 'FeatureClass':
                fld, alias, ftype, flen, indomain, outdomain, src, _, convert_type = row[:9]
            elif desc['dataType'] == 'Table':
                fld, alias, ftype, indomain, outdomain, src, convert_type = row[1:-1]
                flen = None
            else:
                arcpy.AddError(f"Data type {desc['dataType']} is wrong!")
                sys.exit()

            if not fld in exclided_fields:
                fields_to_add.append([fld, ftype, alias, flen])
##                fields_to_add.append([fld, ftype, alias, flen, None, domain])
            if not src in exclided_fields:
                src_flds_dic[src] = [convert_type, indomain]
                src_out_names[src] = fld

        # Check whether each field from the list of source fields exists in the layer.
        # If a field does not exist, remove the field from the list.   
        fields_in_tab = [f for f in list(src_flds_dic.keys()) if f in all_fields]

        # Add objectid field to beginning of lists and dictionary
        fields_in_tab.insert(0,'OID@')
        fields_to_add.insert(0,'ID')

        #
        src_out_names['OID@'] = 'ID'
        
        ######################################################
        #              Starting convert process
        ######################################################

        # Create pandas dataframe from layer or table
        #arcpy.AddMessage('Create pandas dataframe from layer or table')
        nan = -999
        nvalues = fn.create_null_dict(in_tab, nan)
        arr = arcpy.da.TableToNumPyArray(in_tab, fields_in_tab, null_value=nvalues)
        tab_df = pd.DataFrame(data=arr)

        # Convert values from text fields to numeric code fields using domains
        #arcpy.AddMessage('Convert values from text fields to numeric code fields using domains')
        for fld in fields_in_tab[1:]:
            if src_flds_dic[fld][0] == 'TDN':
                domName = src_flds_dic[fld][1]   
                d = fn.df2dict(domains_df, 'Domain Name', domName, 'Description', 'Code')
                tab_df['xxx'] = tab_df[fld].map(d)
                tab_df[fld] = tab_df['xxx']
            elif src_flds_dic[fld][0] == 'TN': # change data type from text to integer
                tab_df['xxx'] = pd.to_numeric(tab_df[fld], errors='coerce', downcast="integer")

                # The type of these fields ('speciesComposition', 'CoverType', 'DominTree')
                # is SHORT therefore max value is  32767
                # In this code, values greater than 50000 must be reduced until they are less than 32767
                if fld in ['speciesComposition', 'CoverType', 'DominTree']:
                    #tab_df.loc[tab_df['xxx']> 50000, 'xxx'] == tab_df['xxx'] - 20000
                    tab_df['xxx'] = np.where(tab_df['xxx'] > 50000, tab_df['xxx'] - 20000, tab_df['xxx'])
                tab_df[fld] = tab_df['xxx']

        tab_df = tab_df.drop(columns='xxx')

        # Change column names
        #
        arcpy.AddMessage(f' BEFORE:\n {tab_df.columns}')
        
        
        tab_df = tab_df.rename(columns=src_out_names)
        arcpy.AddMessage(f' AFTER:\n {tab_df.columns}')

        # Export datframe to csv file
        out_df = tab_df.replace({nan: np.nan, 'None': np.nan})
        out_df.to_csv(converted_csv, index=False, encoding='cp1255')

        # Delete fields in origin table    
        for fld in fields_to_delete:
            arcpy.management.DeleteField(in_tab, fld)   
        #arcpy.AddMessage(f'{len(fields_to_delete)} fields deleted in origin table')
        
        # Create a new temporary table
        if arcpy.Exists(os.path.join(out_gdb,'XXCNVT')):
            arcpy.management.Delete(os.path.join(out_gdb,'XXCNVT'))

        arcpy.management.CreateTable(out_gdb, 'XXCNVT')
        
        # Add a new fields to the temporary table
        arcpy.management.AddFields('XXCNVT', fields_to_add)
        #arcpy.AddMessage(f'{len(fields_to_add)} new fields added to origin table')

        # Append data from csv file to the table
        #arcpy.AddMessage('Append converted data to temp standalone table')
        arcpy.management.Append(converted_csv, 'XXCNVT', 'NO_TEST')

        #arcpy.AddMessage('Join converted fields to dataset')
        oid_fieldname = arcpy.Describe(in_tab).OIDFieldName # update 03/01/2024
        joined_tab = arcpy.management.JoinField(in_tab, oid_fieldname, 'XXCNVT', 'ID')

        # Delete ID field
        arcpy.management.DeleteField(in_tab, 'ID')
        return
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        arcpy.AddError(e)
        arcpy.AddError(f'{exc_type} {fname} {exc_tb.tb_lineno}')
        sys.exit()

def create_domains(df, gdb):
    try:
        # Get list of domains
        domains = df[['Domain Name', 'DataType']].drop_duplicates()
        #codeField, descField = ['Code', 'Description']
        for row in domains.itertuples(False):
            domName = row[0]
            if domName != 'CovtypeSpeciesProportion':
                arcpy.AddMessage(domName)            
                ftype = row[1]
                arcpy.management.CreateDomain(gdb, domName, domName, ftype, "CODED")
                if domName != 'COVTYPE':
                    ddf = df[df['Domain Name']== domName][['Code', 'Description']]
                else:
                    ddf = df[df['Domain Name']== domName][['DomainID', 'Description']]
                for row in ddf.itertuples(False):
                    code = row[0]
                    val = row[1]
                    arcpy.management.AddCodedValueToDomain(gdb, domName, code, val)

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        arcpy.AddError(e)
        arcpy.AddError(f'{exc_type} {fname} {exc_tb.tb_lineno}')

    
if __name__=='__main__':

    try:

        aprx = 'CURRENT'
        p = arcpy.mp.ArcGISProject(aprx)
        proj_dir = p.homeFolder
        proj_gdb = p.defaultGeodatabase

        in_gdb = arcpy.GetParameterAsText(0)
        flag_keep = arcpy.GetParameter(1)

        in_gdb_name = os.path.basename(in_gdb)
        for_no = in_gdb_name.split("_")[1]

        # --------------------------------------------------------------
        #                   Check forest number
        # --------------------------------------------------------------

        # Create list of forest numbers
        regions = os.path.join(proj_gdb, 'ForestRegions')
        for_no_list = []
        if arcpy.Exists(regions):        
            with arcpy.da.SearchCursor(regions, ['forest_id']) as rows:
                for row in rows:
                    for_no_list.append(str(row[0]))
        else:
            arcpy.AddWarning('Cannot create forest number list.\nForestRegion layer does not exist.')
            sys.exit()

        if not for_no in for_no_list:
            arcpy.AddWarning(f'Forest number {for_no} does not exist')
            sys.exit()           
            
        # Flag setting
        flagDel = True

        input_dir = os.path.join(proj_dir, 'SMYDATA')
        appdata_dir = os.path.join(proj_dir,'AppData')
        output_dir = os.path.join(proj_dir,'OUTPUT')
            
        in_gdb = os.path.join(input_dir, in_gdb_name)

        arcpy.env.workspace = in_gdb

        in_points = arcpy.ListFeatureClasses('smy_*', 'Point')[0]
        in_stands = f'stands_{for_no}_fnl'

        if not arcpy.Exists(in_stands):
            arcpy.AddWarning(f'Feature class {in_stands} does not exist!')
            sys.exit()
        
        # Output setting
        out_gdb_name = f'smy{for_no}.gdb'
        keep_gdb_name = f'smy{for_no}_keep.gdb'
        csv_name = f'cnvt{for_no}.csv'
        out_gdb = os.path.join(output_dir, out_gdb_name)
        keep_gdb = os.path.join(output_dir,keep_gdb_name)

        converted_csv = os.path.join(output_dir, csv_name)

        out_points = 'samples'
        out_stands = 'stands'

        # Data design setting
        sheets = ['Samples', 'Stands', 'Tables']
        domain_data_sheet = 'in_domain_data'
        out_domain_sheet = 'out_domain_data'
        rc_sheet = 'RC'
        tables_sheet = 'Tables'
        
        # Get design data 
        ddfile= os.path.join(appdata_dir, 'smy_data_design.xlsx')
                
        domains_df = pd.read_excel(ddfile, domain_data_sheet, index_col=0)
        out_domains_df = pd.read_excel(ddfile, out_domain_sheet)
        rc_df = pd.read_excel(ddfile, rc_sheet)
        
        # Create list of [dataset, field, domain],
        # that will used to assign domain to field in output dataset
        assign_domains =[]        
        for sheet in sheets:
             design_df = fn.fromExcel(ddfile, sheet)
             for row in design_df[design_df['outDomain'].notnull()].itertuples(False):
                if sheet in ['Samples', 'Stands']:
                    fld, alias, ftype, flen, indomain, outdomain, src, _, convert_type = row[:9]
                    assign_domains.append([sheet, fld, outdomain])
                    #arcpy.AddMessage([sheet, fld, outdomain])
                else:
                    tabname, fld, alias, ftype, indomain, outdomain, src, convert_type = row[:-1]
                    assign_domains.append([tabname, fld, outdomain])
                    #arcpy.AddMessage([tabname, fld, outdomain])


        arcpy.AddMessage ('#########################################################')
        arcpy.AddMessage (f'# CMY Data converting process for forest number {for_no}')
        arcpy.AddMessage ('#########################################################')

        ########################################################################
        #         Create a new file geodatabase with conventional names 
        ########################################################################

        associated_data = ";".join([
                                f"{in_points}__ATTACH TableDataset {out_points}__ATTACH #",
                                f"StartRepeatDominTree TableDataset {out_points}_StartRepeatDominTree #",
                                f"VitalForest TableDataset {out_points}_VitalForest #",
                                f"InvasiveSpecies TableDataset {out_points}_InvasiveSpecies #",
                                f"PlantTypeCoverDistribut TableDataset {out_points}_PlantTypeCoverDistribut #",
                                f"{in_points}_VitalForest RelationshipClass RC_{out_points}_VitalForest #",
                                f"{in_points}__ATTACHREL RelationshipClass {out_points}__ATTACHREL #",
                                f"{in_points}_StartRepeatDominTree RelationshipClass RC_{out_points}_StartRepeatDominTree #",
                                f"{in_points}_InvasiveSpecies RelationshipClass RC_{out_points}_InvasiveSpecies #",
                                f"{in_points}_PlantTypeCoverDistribut RelationshipClass RC_{out_points}_PlantTypeCoverDistribut #",                                                         
                                f"{in_stands} FeatureClass {out_stands} #",
                                f"{in_stands}_{in_points} RelationshipClass RC_{out_stands}_{out_points} #",
                                f"{in_stands}_PlantTypeCoverDistribut TableDataset {out_stands}_PlantTypeCoverDistribut #",
                                f"{in_stands}_VitalForest TableDataset {out_stands}_VitalForest #",
                                f"{in_stands}_InvasiveSpecies TableDataset {out_stands}_InvasiveSpecies #",
                                f"{in_stands}_StartRepeatDominTree TableDataset {out_stands}_StartRepeatDominTree #",
                                f"{in_stands}_{in_stands}_PlantTypeCoverDistribut RelationshipClass RC_{out_stands}_PlantTypeCoverDistribut #",
                                f"{in_stands}_{in_stands}_VitalForest RelationshipClass RC_{out_stands}_VitalForest #",
                                f"{in_stands}_{in_stands}_InvasiveSpecies RelationshipClass RC_{out_stands}_InvasiveSpecies #",
                                f"{in_stands}_{in_stands}_StartRepeatDominTree RelationshipClass RC_{out_stands}_StartRepeatDominTree #",
                                ])
        
        if arcpy.Exists(out_gdb):
            arcpy.management.Delete(out_gdb)        

        # Create a new file geogatabase
        arcpy.management.CreateFileGDB(output_dir, out_gdb_name)
        arcpy.AddMessage (f'file geodatabase {out_gdb_name} created')

        arcpy.env.workspace = out_gdb
        arcpy.env.overwriteOutput = 1

        #==========================================================
        arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(2039)
        arcpy.env.geographicTransformations = 'WGS_1984_To_Israel_CoordFrame' # wkid=108021
        #==========================================================

        arcpy.management.Copy(os.path.join(in_gdb, in_points), os.path.join(out_gdb, out_points), associated_data = associated_data)
        arcpy.AddMessage (f'All data copied to {out_gdb_name}')


        ###################   For test only
        lyr = 'test'
        arcpy.management.MakeFeatureLayer(os.path.join(out_gdb, out_points), lyr, 'FOR_NO IS NULL')
        cnt = arcpy.management.GetCount(lyr)[0]
        arcpy.AddMessage( f'{cnt} FOR_NO IS NULL')
        del lyr
        ######################
        
        arcpy.AlterAliasName(out_points, out_points)
        arcpy.AlterAliasName(out_stands, out_stands)


        # Create backup copy of converted gdb
        if flag_keep:
            if arcpy.Exists(keep_gdb):
                arcpy.management.Delete(keep_gdb)
            arcpy.management.Copy(out_gdb, keep_gdb)
            arcpy.AddMessage('Backup a new gdb after data copied')

        # Converting data in a layer

        for layer in ['Samples', 'Stands']:        
            arcpy.AddMessage(f'>>> Converting data in a {layer} layer...')
            design_df = fn.fromExcel(ddfile, layer)
            if layer == 'Samples':           
                arcpy.DisableEditorTracking_management(layer,
                                           "DISABLE_CREATOR",
                                           "DISABLE_CREATION_DATE",
                                           "DISABLE_LAST_EDITOR",
                                           "DISABLE_LAST_EDIT_DATE")

            convert_data(out_gdb, layer, domains_df, design_df, converted_csv)
        # Convert data in tables
        tables_df = fn.fromExcel(ddfile, tables_sheet)
        tables = list(tables_df['Table Name'].drop_duplicates().values)
        for in_tab in tables:
            arcpy.AddMessage(f'>>> Converting data in a {in_tab} table...')
            tab_design_df = tables_df[tables_df['Table Name'] == in_tab]
            if in_tab.split('_')[0] == 'samples':
                arcpy.DisableEditorTracking_management(in_tab,
                                           "DISABLE_CREATOR",
                                           "DISABLE_CREATION_DATE",
                                           "DISABLE_LAST_EDITOR",
                                           "DISABLE_LAST_EDIT_DATE")
                
            convert_data(out_gdb, in_tab, domains_df, tab_design_df, converted_csv)

            # Delete rows with stand_IDs is NULL
            if in_tab.split('_')[0].lower() == 'stands':
                xxtabview = 'nullrows'
                expr = 'stand_ID IS NULL'
                arcpy.MakeTableView_management(in_tab, xxtabview)
                arcpy.SelectLayerByAttribute_management(xxtabview, "NEW_SELECTION", expr)
                cnt = int(arcpy.GetCount_management(xxtabview)[0])
                if cnt > 0:
                    arcpy.management.DeleteRows(xxtabview)
                    arcpy.AddMessage(f'{cnt} rows with stand_ID is null deleted.')
                del xxtabview

        # Delete temporary data
        if flagDel:
            if arcpy.Exists(os.path.join(out_gdb,'XXCNVT')):
                arcpy.management.Delete(os.path.join(out_gdb,'XXCNVT'))

            if arcpy.Exists(converted_csv):
                arcpy.management.Delete(converted_csv)
            arcpy.AddMessage('Temporary data deleted')
            
        # Delete all old domains
        fn.delete_all_domains(out_gdb)

        # Add new domains from data design file
        create_domains(out_domains_df, out_gdb)

        # Assign domains to fields
        for row in assign_domains:
            tab, fld, dom = row
            arcpy.AddMessage(f'>>> Assign domain {dom} to {fld} in a {tab}...')                    
            arcpy.management.AssignDomainToField(tab, fld, dom)

        
        # Delete relationship classes 
        for root, dirs, rcs in arcpy.da.Walk(datatype='RelationshipClass'):
            for rc in rcs:
                if 'RC' in rc:
                    arcpy.management.Delete(rc)
        arcpy.AddMessage('Relationship classes deleted')

        # Create relationship classes and set split policy if need
        for row in rc_df.itertuples(False):            
            arcpy.management.CreateRelationshipClass(row.originClassNames,
                                                     row.destinationClassNames,
                                                     row.name,
                                                     row.Type,
                                                     row.forwardPathLabel,
                                                     row.backwardPathLabel,
                                                     row.notification,
                                                     row.cardinality,
                                                     'NONE',
                                                     row.originPrimaryKey,
                                                     row.originForeignKey)
            # Set split policy
            if row.originClassNames == 'stands' and row.destinationClassNames != 'samples':
                arcpy.management.SetRelationshipClassSplitPolicy(row.name, 
                                                "DUPLICATE_RELATED_OBJECTS")

            arcpy.AddMessage(f'>>> Relationship class {row.name} created')    

        ################
        # Update values
        ################
        #
        # For stands and samples layers
        # 1. Update ForestVegForm, GroundLevelFloorVegForm, primary_VegForm values
        #       9999 -> 9990
        #       2000 -> 2900
        # 2. Update TmiraForestVegForm, secondary_VegForm values
        #       9999 -> Null
        #       9990 -> Null
        # 3. Update CoverType values by newcodes table
        #
        # For samples_StartRepeatDominTree ans stands_StartRepeatDominTree
        # 4. Update spc by newcodes table

        upd_flds = ['ForestVegForm', 'GroundLevelFloorVegForm',
                     'primary_VegForm', 'TmiraForestVegForm',
                     'secondary_VegForm', 'CoverType']

        sht = 'newcodes'
        df = pd.read_excel(ddfile, sht)    
        
        dom_colunm = 'SDE_DOMAIN'

        dom = 'smyCoverType'
        CoverType_dic = {}
        for old, new in df[df[dom_colunm] == dom][['OLDCODE', 'CODE']].itertuples(False):
            CoverType_dic[old] = new        
        oldCoverType_list = sorted(list(CoverType_dic.keys()))

        dom = 'smySpeciesList'
        Species_dic = {}
        for old, new in df[df[dom_colunm] == dom][['OLDCODE', 'CODE']].itertuples(False):
            Species_dic[old] = new        
        oldSpecies_list = sorted(list(Species_dic.keys()))
        
        edit = arcpy.da.Editor(out_gdb)
        edit.startEditing()
        edit.startOperation()

        for layer in ['samples', 'stands']: 
            with arcpy.da.UpdateCursor(layer, upd_flds) as uCur:  
                for row in uCur:
                    for i in range(len(row)):
                        if row[i] != None:                            
                            if upd_flds[i] in ['ForestVegForm', 'Primary_VegForm', 'GroundLevelFloorVegForm']:
                                if row[i] == 9999:
                                    arcpy.AddMessage(f'{layer} old code: {row[i]} {upd_flds[i]} 9990')
                                    row[i] = 9990
                                elif row[i] == 2000:
                                    arcpy.AddMessage(f'{layer} old code: {row[i]} {upd_flds[i]} 2900')
                                    row[i] = 2900
                            elif upd_flds[i] in  ['secondary_VegForm', 'TmiraForestVegForm']:
                                if row[i] in [9999, 9990]:
                                    arcpy.AddMessage(f'{layer} old code: {row[i]} {upd_flds[i]} None')
                                    row[i] = None
                            elif upd_flds[i] == 'CoverType':
                                if row[i] in oldCoverType_list:
                                    arcpy.AddMessage(f'{layer} old code: {row[i]} {upd_flds[i]} {CoverType_dic[row[i]]}')
                                    row[i] = CoverType_dic[row[i]]
                    uCur.updateRow(row)
                

        for table in ['samples_StartRepeatDominTree', 'stands_StartRepeatDominTree']:
            with arcpy.da.UpdateCursor(table, ['spc']) as uCur:  
                for row in uCur:
                    if row[0] in oldSpecies_list:
                        arcpy.AddMessage(f'{table} old code: {row[0]} spc {Species_dic[row[0]]}')
                        row[0] = Species_dic[old]
                    uCur.updateRow(row)                                    
        edit.stopOperation()
        edit.stopEditing(True)
        
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        arcpy.AddError(e)
        arcpy.AddError(f'{exc_type} {fname} {exc_tb.tb_lineno}')


