# -*- coding: utf-8 -*-

import os
import sys
import arcpy
import pandas as pd
import numpy as np

def create_null_dict(tab, val):
    d = {}
    ftypes = ['Integer', 'SmallInteger', 'Double', 'Single']
    flds = [f.name for f in arcpy.ListFields(tab) if f.type in ftypes]
    for f in flds:
        d[f] = val
    return d
    
def fromExcel(xlsfile, sheet_name):
    df = pd.read_excel(xlsfile, sheet_name, index_col = 0)
    return df


def get_uv(tab, field):
    arr = arcpy.da.TableToNumPyArray(tab, [field])
    df = pd.DataFrame(data=arr)
    print(df[field].drop_duplicates())
    return


def df2dict(df, filter_fld, filter_value, keyfld, valuefld):
    d ={}
    df1 = df[df[filter_fld] == filter_value][[keyfld, valuefld]]
    for row in df1.itertuples(index=False):
        d[row[0]] = row[1]    
    return d

def getRelationshipClassesList(workspace):
    ws_children = arcpy.Describe(workspace).children
    rc_list = [c.name for c in ws_children if c.datatype == "RelationshipClass"]
    return rc_list 


def rc_properties2dataframe(workspace):

    # Properties

    rc_list = getRelationshipClassesList(workspace)
    card_dic = {'OneToOne':'"ONE_TO_ONE"', 'OneToMany':'"ONE_TO_MANY"', 'ManyToMany': '"MANY_TO_MANY"'}
    rc_properies=[]
    columns = ['rc_name','originTable','destinTable', 'RCtype', 'notifMsg', 'forwLabel',
               'backLabel', 'RCattr', 'originPrimKey', 'originForinKey',
               'desinPrimKey', 'desinForinKey']
    for rc in rc_list:
        rcpath = os.path.join(workspace, rc)
        desc = arcpy.Describe(rcpath)
        print(rc)
        if desc.isComposite:
            rctype = "COMPOSITE"
        else:
            rctype = "SIMPLE"
        
        if desc.notification == None:
            message_direction= "NONE"
        else:
            message_direction = desc.notification

        if desc.isAttributed:
            rcattr = "ATTRIBUTED"
        else:
            rcattr = "NONE"
    
        if len(desc.destinationClassKeys) > 0:
            dsn_prim_key = desc.destinationClassKeys[0][0]
            dsn_fori_key = destinationClassKeys[1][0]
        else:
            dsn_prim_key = ""
            dsn_fori_key = ""
            
        prop = [ rc, desc.originClassNames[0], desc.destinationClassNames[0], rctype,
                message_direction, desc.forwardPathLabel, desc.backwardPathLabel,
                rcattr, desc.originClassKeys[0][0], desc.originClassKeys[1][0],
                dsn_prim_key, dsn_fori_key]
        
        print(desc.originClassKeys)
        rc_properies.append(prop)

    df = pd.DataFrame(data= rc_properies, columns=columns)
    
    return df

def criateRC(param):
    relClass = 'rc1'
    origin_table=r'C:\MDGISS\devs\SEMI\semi_to_stnd.gdb\smy_Um_El_Phahem'
    destination_table=r'C:\MDGISS\devs\SEMI\semi_to_stnd.gdb\InvasiveSpecies'
    relationship_type="COMPOSITE"
    forward_label=""
    backward_label=""
    message_direction=None
    Cardinality="ONE_TO_MANY"
    Attributed="NONE"
    origin_primary_key='globalid'
    origin_foreign_key='parentglobalid'


    arcpy.management.CreateRelationshipClass(origin_table,
                                             destination_table,
                                             relClass,
                                             relationship_type,
                                             forward_label,
                                             backward_label,
                                             message_direction,
                                             Cardinality,
                                             Attributed,
                                             origin_primary_key,
                                             origin_foreign_key)
    return


def delete_all_domains(gdb):
    domains = [ d.name for d in arcpy.da.ListDomains(gdb)]
    for d in domains:
        arcpy.management.DeleteDomain(gdb, d)
    return

def all_domains2csv(gdb, csvfile):
    # Get data of domains
    import os
    import arcpy

    arcpy.env.workspace = gdb
    arcpy.env.overwriteOutput = 1
    
    tab = 'xxxdom'
    codeField = 'Code'
    fieldDesc = 'Description'
    domains = arcpy.da.ListDomains(gdb)
    dlist =[]
    for d in domains:
        dn = d.name
        print (dn)
        arcpy.DomainToTable_management(gdb, d.name, tab , codeField, fieldDesc)
        arr = arcpy.da.TableToNumPyArray(tab, [codeField, fieldDesc])
        df = pd.DataFrame(data=arr)
        df['Domain'] = dn
        dlist.append(df)

    df_all = pd.concat(dlist)
    df_all.to_csv(csvfile, encoding='1255')
    return

def create_fc(gdb, in_fc, out_fc, df):
    '''
    gdb: File geodatabase, where will be created a new feature class
    fc : A new feature class name
    df : Pandas dataframe with desing data   
    '''

    arcpy.env.workspace = gdb
    
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)

    fmap = get_only_required_fmap(in_fc)
    arcpy.conversion.FeatureClassToFeatureClass(in_fc, gdb, out_fc, '', fmap)
    

    for row in df.itertuples(False):
        print(row[0], row[1], row[2])
        fld_name = row[0]
        fld_alias = row[1]
        fld_type = row[2].capitalize()

        if fld_type == 'TEXT':
            fld_length = row[3]
        else:
            fld_length = ""                
        fld_domain = row[4]
        print (fld_name, fld_domain)
        arcpy.management.AddField(out_fc, fld_name, fld_type, "", "", fld_length,
                                  fld_alias, "", "", fld_domain)
    return



def get_only_required_fmap(in_fc):

    fmap = arcpy.FieldMappings()
    fmap.addTable(in_fc)

    # get all not required fields
    fields = [f.name for f in arcpy.ListFields(in_fc) if not f.required]

    # clean up field map
    for fname in fields:       
        fmap.removeFieldMap(fmap.findFieldMapIndex(fname))
    return fmap 

def add_domains(df, out_gdb, csvfile):

    # Get list of domains
    domains = df[['Domain Name', 'DataType']].drop_duplicates()
    codeField, descField = ['Code', 'Description']
    for row in domains.itertuples(False):
        domName = row[0]
        if domName != 'CovtypeSpeciesProportion':
            ftype = row[1]
            print(domName)
            ddf = df[df['Domain Name']== domName][[codeField, descField]]
            ddf.to_csv(csvfile, index=False, encoding='cp1255')
            arcpy.management.TableToDomain(csvfile, codeField,
                                           descField, out_gdb, domName, domName)
    return


def create_domains(df, gdb):
    try:
        # Get list of domains
        domains = df[['Domain Name', 'DataType']].drop_duplicates()
        codeField, descField = ['Code', 'Description']
        for row in domains.itertuples(False):
            domName = row[0]
            if domName != 'CovtypeSpeciesProportion':
                print(domName)            
                ftype = row[1]
                arcpy.management.CreateDomain(gdb, domName, domName, ftype, "CODED")
                ddf = df[df['Domain Name']== domName][[codeField, descField]]
                for row in ddf.itertuples(False):
                    code = row[0]
                    val = row[1]
                    arcpy.management.AddCodedValueToDomain(gdb, domName, code, val)

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f'{exc_type} {fname} {exc_tb.tb_lineno}')
        print (e)

    return
##arcpy.management.AssignDomainToField(inFeatures, inField, domName)
##    
##    ##d = {112: 'en', 113: 'es', 114: 'es', 111: 'en'}
##    ##df['D'] = df['U'].map(d)
##
##    # convert column "a" of a DataFrame
##    # df["a"] = pd.to_numeric(df["a"])

  
    
########################
#       TESTING
########################

if __name__=='__main__':

    aprx = r'C:\MDGISS\devs\SEMI\semi_to_stnd.aprx'
    p = arcpy.mp.ArcGISProject(aprx)
    proj_dir = p.homeFolder

    in_gdb = r'C:\MDGISS\devs\SEMI\SEMIDATA\UmElPhahem_3408_fnlStands_260623.gdb'
    in_tab = r'C:\MDGISS\devs\SEMI\OUTPUT\smy3408.gdb\samples_test'
    in_tab = r'C:\MDGISS\devs\SEMI\OUTPUT\smy3408.gdb\samples'
    in_fld = 'speciesComposition'
    
    csv = r'C:\MDGISS\devs\SEMI\OUTPUT\relationship_classes.csv'
    domcsvfile = r'C:\MDGISS\devs\SEMI\OUTPUT\data_domains.csv'
    domcsv = r'C:\MDGISS\devs\SEMI\OUTPUT\xxdomains.csv'
    converted_data_csv = r'C:\MDGISS\devs\SEMI\OUTPUT\cnvt.csv'

    data_dir = os.path.join(proj_dir, 'SEMIDATA')
    appdata_dir = os.path.join(proj_dir,'AppData')
    output_dir = os.path.join(proj_dir,'OUTPUT')
    out_gdb = os.path.join(output_dir, 'smy3408.gdb')
    keep_gdb = os.path.join(output_dir, 'smy3408_keep.gdb')

    # Data design setting
    ddfile= os.path.join(appdata_dir, 'smy_data_design.xlsx')    
    domain_data_sheet = 'out_domain_data'
    tab_desing_sheet = 'Samples'
    domains_df = fromExcel(ddfile, domain_data_sheet)

    

##    # Get list of layer or table fields
##    arcpy.env.workspace = out_gdb
##
##    #add_domains(domains_df, out_gdb, domcsv)
##    create_domains(domains_df, out_gdb)
##
##    ############################################################
##    # Create lists and dictionaries to manage converting process
##    ############################################################
##    
##    all_fields = [f.name for f in arcpy.ListFields(in_tab)]    
##    rqd_fields = [f.name for f in arcpy.ListFields(in_tab) if f.required]
##    const_fields = ['SiteID', 'Date']
##    read_only_fields = ['CreationDate', 'Creator', 'EditDate', 'Editor', 'stand_ID']
##    exclided_fields = rqd_fields + const_fields + read_only_fields
##
##    # Create list of fields that will be deleted from origin layer or table.
##    fields_to_delete = [ f for f in all_fields if not f in exclided_fields]
##    
##    # Get data design
##    domains_df = fromExcel(ddfile, domain_data_sheet)
    tab_desin_df = fromExcel(ddfile, tab_desing_sheet)
    
    print (tab_desin_df[tab_desin_df[['Domain']].notnull().all(1)][['Field Name', 'Domain']])
##
##    
##    src_out_names ={}   # Will used to rename column names 
##    src_flds_dic = {}   # Will used to convert fields values
##    fields_to_add = []  # Will used to add 'kkl' fields to a standalone table
##
##    print('Creating lists and dictionaries to manage converting process')
##    for row in tab_desin_df.itertuples(False):
##        fld = row[0]
##        alias = row[1]
##        ftype = row[2]
##        flen = row[3]
##        domain = row[4]
##        src = row[5]        
##        convert_type = row[7]
##        
##        if not fld in exclided_fields:
##            fields_to_add.append([fld, ftype, alias, flen, None, domain])
##        if not src in exclided_fields:
##            src_flds_dic[src] = [convert_type, domain]
##            src_out_names[src] = fld
##
##    # Check whether each field from the list of source fields exists in the layer.
##    # If a field does not exist, remove the field from the list.   
##    fields_in_tab = [f for f in list(src_flds_dic.keys()) if f in fields]
##
##
##    # Add objectid field to beginning of source field list
##    fields_in_tab.insert(0,'OID@')
##    fields_to_add.insert(0,'ID')
##    src_out_names['OID@'] = 'ID'
##    
##    ######################################################
##    #              Starting convert process
##    ######################################################
##
##    # Create pandas dataframe from layer or table
##    print('Create pandas dataframe from layer or table')
##    arr = arcpy.da.TableToNumPyArray(in_tab, fields_in_tab)
##    tab_df = pd.DataFrame(data=arr)
##
##    # Convert values from text fields to numeric code fields using domains
##    print('Convert values from text fields to numeric code fields using domains')
##    for fld in fields_in_tab[1:]:
##        if src_flds_dic[fld][0] == 'TDN':
##            domName = src_flds_dic[fld][1]   
##            d = df2dict(domains_df, 'Domain Name', domName, 'Description', 'Code')
##            tab_df['xxx'] = tab_df[fld].map(d)
##            tab_df[fld] = tab_df['xxx']
##        elif src_flds_dic[fld][0] == 'TN': # change data type from text to integer
##            tab_df['xxx'] = pd.to_numeric(tab_df[fld], errors='coerce', downcast="integer")
##            tab_df[fld] = tab_df['xxx']
##
##    tab_df = tab_df.drop(columns='xxx')
##
##    # Change column names
##    tab_df = tab_df.rename(columns=src_out_names)
##
##    # Export datframe to csv file
##    tab_df.to_csv(converted_data_csv, index=False, encoding='cp1255')
##
##    # Create backup copy of converted gdb
##    if not arcpy.Exists(keep_gdb):
##        arcpy.management.Copy(out_gdb, keep_gdb)
##    
##
##    # Delete fields in origin table    
##    for fld in fields_to_delete:
##        arcpy.management.DeleteField(in_tab, fld)   
##    print(f'{len(fields_to_delete)} fields deleted in origin table')
##    
##    # Create a new temporary table
##    arcpy.management.CreateTable(out_gdb, 'XXCNVT')
##    
##    # Add a new fields to the temporary table
##    arcpy.management.AddFields('XXCNVT', fields_to_add)
##    print(f'{len(fields_to_add)} new fields added to origin table')
##
##    # Append data from csv file to the table
##    print('Append converted data to temp standalone table')
##    arcpy.management.Append(converted_data_csv, 'XXCNVT', 'NO_TEST')
##
##    print('Join data to layer')
##    joined_tab = arcpy.management.JoinField(in_tab, 'objectid', 'XXCNVT', 'ID')
    
    
