import sys
import os
import arcpy
import pandas as pd
import numpy as np
import zipfile

import smy_functions as fn


def getnull(oid):
    nullRows.append(oid)
    return True


def open_zip(zfile, out_dir):
    with zipfile.ZipFile(zfile,'r') as zip_ref:
        zip_ref.extractall(out_dir)
        return

def domains2csv(in_gdb, out_csv=None):
    out_list = []
    for d in arcpy.da.ListDomains(gdb):
        n = d.name
        cv_dic = d.codedValues
        for k, v in cv_dic.items():
            out_list.append([n,k,v])

    arr = np.array(out_list)
    df = pd.DataFrame(data=np.array(out_list), columns=['Name', 'Code', 'Value'])
    if out_csv:
        df.to_csv(out_csv, encoding='1255')
    else:
        for n, k, v in out_list:
            arcpy.AddMessage (f'{n}\t{k}\t{v}')
    
    return

def check_is_digit(tab):
    return

if __name__=='__main__':
    
    try:
        '''
        1. Checking presence of data items and their names.
        2. Checking data structure (presence of fields, their names and types)
        3. Verificaion of field values
        4. Verification data (added 06/08/2024)
        '''    

        aprx = 'CURRENT'
        p = arcpy.mp.ArcGISProject(aprx)
        proj_dir = p.homeFolder
        proj_gdb = p.defaultGeodatabase

        # --------------------------------------------
        #             Setting parameters
        # --------------------------------------------

        gdb = arcpy.GetParameterAsText(0)

        gdb_name = os.path.basename(gdb)
        for_no = gdb_name.split('_')[1]

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
    
        
        data_dir = os.path.join(proj_dir, 'SMYDATA')
        appdata_dir = os.path.join(proj_dir,'AppData')
        output_dir = os.path.join(proj_dir,'OUTPUT')

        # Data design file
        data_design_file= os.path.join(appdata_dir, 'smy_data_design.xlsx')    

        # Output
        vrfc_file = os.path.join(output_dir, f'verification_report_{for_no}.csv')

        arcpy.env.workspace = gdb

        data_list =[]

        ############################################################
        #   1. Checking presence of data items and their names.
        ############################################################
        
        arcpy.AddMessage('############################################################')
        arcpy.AddMessage('#   1. Checking presence of data items and their names.')
        arcpy.AddMessage('############################################################')
        arcpy.AddMessage('')

        # 1. Points layer
        point_layers = arcpy.ListFeatureClasses('smy_*', 'POINTS')
        if len(point_layers) == 1:        
            points = point_layers[0]
            arcpy.AddMessage (f'\tThe points layer presented: {points}')
            data_list.append(points)   
        else:
            arcpy.AddWarning (f'\tThere should be one points layer with prefix "smy_", not {len(point_layers)}! Stop verification.')
            sys.exit()
            
        points_rtables = [ 'PlantTypeCoverDistribut',
                           'VitalForest',
                           'InvasiveSpecies',
                           'StartRepeatDominTree',
                           f'{points}__ATTACH']

        # check points related tables
        rtables = arcpy.ListTables()
        ptables = []
        for pt in rtables:
            if pt in points_rtables:
                ptables.append(pt)
                if not 'ATTACH' in pt: 
                    data_list.append(pt)
        diff = set(points_rtables) - set(ptables)

        if len(diff) == 0:
            arcpy.AddMessage('\tAll point related tables presented')
        else:
            missing_tables = "\n".join(diff)
            arcpy.AddMessage ('\tPoint related tables are missing:')
            arcpy.AddMessage ( '\t', missing_tables)   

        # 2. Stands layer
        stands_layers =  arcpy.ListFeatureClasses('stand*', 'POLYGONS')
        if len(stands_layers) == 1:        
            stands = stands_layers[0]
            arcpy.AddMessage (f'\tThe stands layer presented: {stands}')
            data_list.append(stands)
        else:
            arcpy.AddError (f'\tThere should be one stands layer, not {len(stands_layers)}! Stop verification.')
            sys.exit()
        
        stands_rtables = arcpy.ListTables(f'{stands}*')
        stables = []
        check_stands_rtables = []
        for st in stands_rtables:
            
            if 'PlantTypeCoverDistribut' in st:
                check_stands_rtables.append('PlantTypeCoverDistribut')
                data_list.append(st)
            elif 'VitalForest' in st:
                check_stands_rtables.append('VitalForest')
                data_list.append(st)
            elif 'InvasiveSpecies' in st:
                check_stands_rtables.append('InvasiveSpecies')
                data_list.append(st)
            elif 'StartRepeatDominTree' in st:
                check_stands_rtables.append('StartRepeatDominTree')
                data_list.append(st)
        diff = set(points_rtables[:-1]) - set(check_stands_rtables)

        if len(diff) == 0:
            arcpy.AddMessage('\tAll stands related tables presented')
        else:
            tt = "\n".join([f'{stands}_{t}' for t in diff])
            arcpy.AddWarning ('\tThese Stands related tables are missing:')
            arcpy.AddWarning ('\t', tt)
            
        # 3. Reletionship classes
        rc_names = [
                    f"{points}_VitalForest", f"{points}__ATTACHREL",
                    f"{points}_StartRepeatDominTree",
                    f"{points}_InvasiveSpecies",
                    f"{points}_PlantTypeCoverDistribut",
                    f"{stands}_{points}",
                    f"{stands}_{stands}_PlantTypeCoverDistribut",
                    f"{stands}_{stands}_VitalForest",
                    f"{stands}_{stands}_InvasiveSpecies",
                    f"{stands}_{stands}_StartRepeatDominTree"]

        curr_rc_names = fn.getRelationshipClassesList(gdb)

        diff = set(rc_names) - set(curr_rc_names)
        if len(diff) == 0:
            arcpy.AddMessage('\tAll relationship classes presented in correct names')
        else:
            tt = "\n".join(diff)
            arcpy.AddWarning (f'\tThese Relationship classes are missing or have incorrect name:')
            arcpy.AddWarning (tt)

        ###########################################################################
        #  2. Checking data structure (presence of fields, their names and types)
        ###########################################################################
        
        arcpy.AddMessage('###########################################################################')
        arcpy.AddMessage('#  2. Checking data structure (presence of fields, their names and types)')
        arcpy.AddMessage('###########################################################################')
        arcpy.AddMessage('')
        # Point layer field checking
        smy_flds_points_df = pd.read_excel(data_design_file, 'Samples' )
        design_point_flds = list(smy_flds_points_df['Field Source'].values)

        presented_points_flds = [f.name for f in arcpy.ListFields(points)]

        diff = set(design_point_flds) - set(presented_points_flds)

        if len(diff) == 0:
            arcpy.AddMessage(f'\tAll fields presented in {points} layer')
        else:
            missing_fields = '\t\t'+'\n\t\t'.join(diff)
            arcpy.AddWarning(f'\tFields are missing in {points}:')
            arcpy.AddWarning(missing_fields)
               
        # Stand layer field checking
        smy_flds_stands_df = pd.read_excel(data_design_file, 'Stands' )
        design_stands_flds = list(smy_flds_stands_df['Field Source'].dropna().values)
        flds_must = list(smy_flds_stands_df['Field Source'][smy_flds_stands_df['mustExist'] == 1].dropna().values)
        presented_stand_flds = [f.name for f in arcpy.ListFields(stands)]

        # Check field presence
        error_list = []
        warning_list = []
        for f in design_stands_flds:
            if not f in presented_stand_flds:
                if f in flds_must:
                    arcpy.AddError (f'\tError! The field {f} must be exist!')
                    error_list.append(f)
                else:
                    arcpy.AddWarning (f'\tWarning! The field {f} does not exist!')

        if len(error_list) > 0:
            raise Exception(f'\tIn layer {stands} there is(are) no {len(error_list)} mandatory field(s): {", ".join(error_list)}') 

        if len(error_list) > 0:
            arcpy.AddMessage(f'\tError! In layer {stands} there is(are) no {len(error_list)} mandatory field(s): {", ".join(error_list)}') 
            sys.exit()

        ######################################
        #  3. Verification of fields values
        ######################################

        arcpy.AddMessage('######################################')
        arcpy.AddMessage('#  3. Verification of fields values')
        arcpy.AddMessage('######################################')
        arcpy.AddMessage('')
        domains_sheet = 'in_domain_data'
        domain_df = fn.fromExcel(data_design_file, domains_sheet)

        check_list = []
        
        for ds in data_list:
            arcpy.AddMessage(f'\tCheck fields values of {ds}')
            ds_flds = [f.name for f in arcpy.ListFields(ds)]
            if ds == points:
                sheet ='Samples'
            elif ds == stands:
                sheet = 'Stands'
            else:
                sheet = 'Tables'
            data_df = fn.fromExcel(data_design_file, sheet)

            # Check if value is digit for each field where ConvertType = 'TN'
            tn_df = data_df[data_df['ConvertType'] == 'TN' ][['Field Source']]


            # 1. ddd is dataframe with Source fields name and domains name for current dataset
            # 2. tn_df is dataframe with  Source fields name,
            #    if value is digit for each field where ConvertType = 'TN'
            if sheet in ['Samples', 'Stands']:
                ddd = data_df[data_df['inDomain'].notnull()][['Field Source', 'inDomain']]
                tn_df = data_df[data_df['ConvertType'] == 'TN' ][['Field Source']]
            else:
                if len(ds.split("_")) > 1:
                    tab_name = f'stands_{ds.split("_")[-1]}'
                else:
                    tab_name = f'samples_{ds.split("_")[-1]}'
                    
                ddd = data_df[(data_df['inDomain'].notna()) & (data_df['Table Name'] == tab_name)][['Field Source', 'inDomain']]        
                tn_df = data_df[(data_df['ConvertType'] == 'TN') & (data_df['Table Name'] == tab_name)][['Field Source']]

                               
            for row in ddd.itertuples(False):
                fld_name = row[0]
                if fld_name in ds_flds:
                    domain_name = row[1]    
                    vlist = domain_df[domain_df['Domain Name']== domain_name]['Description'].values
                    
                    with arcpy.da.SearchCursor(ds, ['OID@', fld_name]) as sCur:
                        values = {}
                        for row in sCur:
                            oid  = row[0]
                            value = row[1]
                            if (not value in vlist) and (value != None) and (value != ''):
                                if value in values:
                                    values[value].append(oid)
                                else:
                                    values[value]=[oid]                                
                else:
                    arcpy.AddWarning(f'\tThe field {fld_name} does not exist in {ds}')
                                
                for v in values:
                    l = [ds, len(values[v]), fld_name, v, domain_name]
                    check_list.append(l)
                                            
                

        if len(check_list) > 0:               
            out_df = pd.DataFrame(data=check_list, columns=['Dataset','OID_cnt','Field', 'Bad Value', 'inDomain'])
            out_df.to_csv(vrfc_file, encoding='1255')
            arcpy.AddWarning(f"\tWarning! The information about 'bad' values saved in {vrfc_file} file.")
        else:
            arcpy.AddMessage("\tDid not find any 'bad' value")

        ########################################################
        #  4. Checking primary and foreign key for samples data
        ########################################################
        checke_flag = True
        arcpy.AddMessage('#########################################################')
        arcpy.AddMessage('#  4. Checking primary and foreign key for samples data')
        arcpy.AddMessage('#########################################################')
        arcpy.AddMessage('')

        foreign_key = 'ParentGlobalID'
        # Create list of GlobalID values of sample layer
        fields = [ 'FOR_NO', 'HELKA', 'STAND_NO', 'GlobalID']
        arr = arcpy.da.TableToNumPyArray(points, fields, null_value=-1)
        df = pd.DataFrame(data=arr)
        gids = list(df['GlobalID'].values)    

        # Check ParentGlobalID
        for tab in points_rtables[:-1]:
            if arcpy.Exists(tab):
                arr = arcpy.da.TableToNumPyArray(tab, [foreign_key], null_value=-1)
                df = pd.DataFrame(data=arr)
                cnt  = len(df[df[foreign_key]=='-1'])
                if cnt > 0:
                    checke_flag = False
                    arcpy.AddWarning(f"\tWarning! The ParentGlobalID field has {cnt} row(s) with <null> value in table {tab}")
                pgids = list(df[df[foreign_key]!='-1'][foreign_key].drop_duplicates().values)
                diff = set(pgids) - set(gids)
                if len(diff) > 0:
                    checke_flag = False
                    arcpy.AddWarning(f"tWarning! The {len(diff)} ParentGlobalID  values of {tab} is not present in {points}")
                    for v in diff:
                        arcpy.AddWarning(f'\t\t{v}')

            if checke_flag:
                arcpy.AddMessage(f'\tParentGlobalID of {tab} is OK') 
            

        #####################################################
        #  5. Checking if forest stand address contain <null>
        #####################################################
        
        arcpy.AddMessage('#####################################################')
        arcpy.AddMessage('#  5. Checking if forest stand address contain <null>')
        arcpy.AddMessage('#####################################################')
        arcpy.AddMessage('')

        for layer in [points, stands]:
            check_fhp = True
            with arcpy.da.SearchCursor(layer, ['FOR_NO', 'HELKA', 'STAND_NO']) as sCur:                
                for row in sCur:
                    if not all(row):
                        check_fhp = False
                        arcpy.AddWarning(f"\tWarning! The {row[0]}_{row[1]}_{row[2]} address of {layer}is not correct!")
            if check_fhp:
                arcpy.AddMessage(f'\t{layer} forest stand address is OK')
            

        #####################################################
        #  6. Checking unique of FHP
        #####################################################
        arcpy.AddMessage('#####################################################')
        arcpy.AddMessage('#  6. Checking unique of stand forest address')
        arcpy.AddMessage('#####################################################')
        fhp_list = []
        duplicated_fhp_list = []
        with arcpy.da.SearchCursor(stands, ['FOR_NO', 'HELKA', 'STAND_NO']) as sCur:                
            for row in sCur:
                fhp = f'{row[0]}_{row[1]}_{row[2]}'
                if not fhp in fhp_list:
                    fhp_list.append(fhp)
                else:
                    if not fhp in duplicated_fhp_list:
                        duplicated_fhp_list.append(fhp)

        if len(duplicated_fhp_list) > 0:
            for fhp in duplicated_fhp_list:
                f_h_p = '\t'.join(fhp.split('_'))
                arcpy.AddWarning(f_h_p)
        else:
            arcpy.AddMessage (f'\tDid not find any duplicates in the forest address of {stands}')

        #####################################################
        # 7. Forest address matching check
        #    between related tables and stands layer
        ####################################################

        csv_out = os.path.join(output_dir,'fhp_mismatch.csv')
        nullRows = list()

        arr = arcpy.da.FeatureClassToNumPyArray(stands, ['GlobalID', 'FOR_NO', 'HELKA', 'STAND_NO'])
        df = pd.DataFrame(data=arr, columns=arr.dtype.names)
        arcpy.AddMessage('########################################################################')
        arcpy.AddMessage('#  7. Forest address mismatching')
        arcpy.AddMessage('#     between related tables and stands layer')
        arcpy.AddMessage('########################################################################')

        arcpy.AddMessage(f'\t{stands}')


        names = [ 'PlantTypeCoverDistribut', 'VitalForest',
                   'InvasiveSpecies', 'StartRepeatDominTree']
        tables = list(map(lambda x: f'{stands}_{x}', names))

        out_columns = ['GlobalID','FOR_NO', 'HELKA', 'STAND_NO','TFOR_NO', 'THELKA', 'TSTAND_NO', 'TABLE']
        df_list =[]

        for table in tables:
            arr = arcpy.da.TableToNumPyArray(table, ['stand_ID','FOR_NO', 'HELKA', 'STAND_NO'], skip_nulls=getnull)

            if len(nullRows)>0:
                arcpy.AddWarning(f'\t{table} have {len(nullRows)} records with NULL in fields of forest adress or key.')               
            
            arr_uniq = np.unique(arr)
            tab_df = pd.DataFrame(data=arr_uniq, columns=arr.dtype.names)
            merge_df = df.merge(tab_df, left_on='GlobalID', right_on='stand_ID')
            diff =[]
            for row in merge_df.itertuples(False):
                if f'{row[1]}_{row[2]}_{row[3]}' != f'{row[5]}_{row[6]}_{row[7]}':
                    diff.append([row[0],row[1],row[2],row[3],row[5],row[6],row[7], table])

            if len(diff)>0:
                arcpy.AddWarning (f'\t{table}: {len(diff)} records mismatched')
                df_list.append(pd.DataFrame(data=diff, columns = out_columns))

        if len(df_list)> 0:
            concat = pd.concat(df_list)                
            concat.to_csv(csv_out)
            arcpy.AddWarning(f'\tAll mismathes  are in the file {csv_out}')
        else:
            arcpy.AddMessage('\tThere are no mismatches forest address.')

        ############################################
        # 8. Check code 9999 in field CoverTypeCode
        ###########################################
        check9999 = True
        flds = ['OID@', 'HELKA', 'STAND_NO','CoverTypeCode']
        arr = arcpy.da.TableToNumPyArray(stands, flds, skip_nulls=getnull)
        arcpy.AddMessage('##############################################')
        arcpy.AddMessage(f'# 8. Check code 9999 in field CoverTypeCode of {stands}')
        arcpy.AddMessage('##############################################')
        for row in arr:
            if row[3] == '9999':
                check9999 = False
                arcpy.AddWarning(f"\tCoverTypeCode = '9999' for oid={row[0]}, helka={row[1]}, stand_no= {row[2]}.")

        if check9999:
            arcpy.AddMessage('\tOK')
                
        ###########################################################
        # 9. Check NULL or 'אין' in fields CoverTypeCode,
        # ForestVegForm, primery_VegForm,  GroundLevelFloorVegForm
        ###########################################################
        check_null = True             
        arcpy.AddMessage('#########################################################################')
        arcpy.AddMessage('# 9. Check NULL or "אין" in fields:')
        arcpy.AddMessage('# CoverTypeCode, ForestVegForm, primary_VegForm, GroundLevelFloorVegForm')
        arcpy.AddMessage('##########################################################################')

        flds_dic = {stands:['OID@', 'HELKA', 'STAND_NO','CoverTypeCode', 'ForestVegForm',
                    'primary_VegForm', 'GroundLevelFloorVegForm'],
                    points: ['OID@', 'HELKA', 'STAND_NO', 'ForestVegForm',
                    'primary_VegForm', 'GroundLevelFloorVegForm']}

        for layer in [points, stands]:
                
            flds = flds_dic[layer]
            arr = arcpy.da.TableToNumPyArray(layer, flds) #, skip_nulls=getnull)
            for row in arr:
                for i in range(3,len(flds)):
                    if row[i] in [None, '', 'אין', 'None']:
                        check_null = False
                        arcpy.AddWarning(f'\tLayer={layer}, field={flds[i]}, oid={row[0]}, helka={row[1]}, stand_no= {row[2]} value= {row[i]}')
        if check_null:
           arcpy.AddMessage('\tOK')
           
        ###########################################################
        # 10. Check NULL, -1, 9999 in field InvasiveSpecie
        # of InvasiveSpecies table
        ###########################################################
        tab = 'InvasiveSpecies'
        tabs = ['InvasiveSpecies', f'{stands}_InvasiveSpicies']
        fld = ['InvasiveSpecie']
        bad_values = ['None','אין','9999']
        
        arcpy.AddMessage('#########################################################################')
        arcpy.AddMessage('# 10. Check NULL, אין, 9999 in field InvasiveSpecie')
        arcpy.AddMessage(f'# of InvasiveSpecies and {stands}_InvasiveSpicies tables')
        arcpy.AddMessage('##########################################################################')
        arr = arcpy.da.TableToNumPyArray(tab, [fld])
        cnt = 0

        for tab in tabs:
            for row in arr:
                if row[0] in bad_values:
                        cnt += 1
            if cnt > 0:
                arcpy.AddMessage(f'\tThe {tab} table have {cnt} rows with values: {bad_values}' )
            else:
                arcpy.AddMessage(f'\tThe {tab} table does not have "bad" values.')

        ###########################################################
        # 11. Check NULL in field totalTreeCover
        # of Samples layer and in field totalCanopyCover
        # of Stands layer 
        ###########################################################
        arcpy.AddMessage('##############################################################')
        arcpy.AddMessage(f'# 11. Check NULL in field totalTreeCover of {points} and in field totalCanopyCover of {stands}')
        arcpy.AddMessage('##############################################################')
        
        for row in [[points, 'totalTreeCover'],[stands, 'totalCanopyCover']]:
            tab = row[0]
            fld = row[1]
            bad_values = ['None']
            if fld in [f.name for f in arcpy.ListFields(tab)]:
                arr = arcpy.da.TableToNumPyArray(tab, [fld])
                cnt = 0
               
                for row in arr:
                    if row[0] in bad_values:
                        cnt += 1
                if cnt > 0:
                    arcpy.AddMessage(f'\tThe layer {tab}  have {cnt} rows with values: {bad_values}' )
                else:
                    arcpy.AddMessage(f'\tThe layer {tab} does not have "bad" values')
            else:
                 arcpy.AddMessage(f'\tThe {fld} does not exist in {tab}!')

        ###########################################################
        # 12. Check values in fields of both layers: primary_layerCover,
        # secondary_layerCover, TmiraLayerCover, HighLayerCover, MidLayerCover
        ###########################################################
        arcpy.AddMessage('######################################################################')
        arcpy.AddMessage('# 12. Check zero values in fields of both layers: primary_layerCover,')
        arcpy.AddMessage('# secondary_layerCover, TmiraLayerCover, HighLayerCover, MidLayerCover')
        arcpy.AddMessage('######################################################################')

        flds = ['primary_layerCover', 'secondary_layerCover',
                'TmiraLayerCover', 'HighLayerCover', 'MidLayerCover']
        
        for tab in [points, stands]:
            d ={fld:0 for fld in flds}
            
            arr = arcpy.da.TableToNumPyArray(tab, [flds])
            for row in arr:
                for i in range(len(row)):
                    if row[i] == 0:
                        d[flds[i]] += 1

            if sum(d.values()) > 0:
                for f in d:
                    if d[f] > 0:
                        arcpy.AddMessage(f'\tThe field {f} in {tab} contains {cnt} rows with values 0' )
            else:
                arcpy.AddMessage(f'\tThe fields in {tab} do not have rows with values 0' )

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        arcpy.AddError(e)
        arcpy.AddError(f'{exc_type} {fname} {exc_tb.tb_lineno}')

        
        
     
