# -*- coding: utf-8 -*-
import os
import arcpy
import arcgisscripting
import time

"""
Notice:
this code supports domains of the type 'coded values' only.
"""

arcpy.env.overwriteOutput = True

debug_mode = False
if debug_mode:
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\אוגוסט 2022\QA\New File Geodatabase.gdb'
    input_excelPath = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\אוגוסט 2022\QA\eexxcceell.xlsx'
    domains_table = os.path.join(input_workspace, 'domains')
    domains_subTable = os.path.join(input_workspace, 'domains_sub')

else:
    input_excelPath = arcpy.GetParameter(0)
    input_workspace = arcpy.GetParameter(1)
    domains_table = os.path.join('in_memory', 'domains')
    domains_subTable = os.path.join('in_memory', 'domains_sub')


arcpy.env.workspace = input_workspace
workspaceDomains = arcpy.da.ListDomains(arcpy.env.workspace)
__domainNames = [d.name for d in workspaceDomains]

#FUNCTIONS
def printDomains(workspace):
    domains = arcpy.da.ListDomains(workspace)
    codedValue_domains = [domain for domain in domains if domain.domainType == 'CodedValue']
    for domain in codedValue_domains:
        name = domain.name
        print(name)
        for code, description in domain.codedValues.items():
            print('~~~code: %s, description:%s' % (code, description))
        print('--------------------------------------')

def exportTable(inputTable, outputTable, whereClause):
    """
    Since arcpy.ExportTable_conversion and arcpy.conversion.exporttable
    don't work, I put down this function as a substitute.
    This function creates a new table (outputTable) with the same
    scheme as inputTable, and inserts new rows based on the whereClause
    given.
    """
    arcpy.CreateTable_management(
        os.path.dirname(outputTable),
        os.path.basename(outputTable),
        inputTable
        )
    sc = arcpy.SearchCursor(inputTable, whereClause)
    ic = arcpy.InsertCursor(outputTable)
    for s_row in sc:
        ic.insertRow(s_row)
    del sc, ic
    return

#PROCESS
#excel to table:
arcpy.ExcelToTable_conversion(input_excelPath, domains_table)

#Create a list of [(domain name <str>, type <str>), ...]
#with the value of 1 in their applyToDatabase column:
domains_toImport = set()
expression = u'{} = 1'.format(arcpy.AddFieldDelimiters(domains_table, 'applyToDatabase'))
sc = arcpy.da.SearchCursor(domains_table,['name', 'type', 'applyToDatabase'],
                           where_clause=expression)
for r in sc:
    name = r[0]
    type_ = r[1].upper()
    toImport = r[2] == 1
    if toImport:
        tup = (name, type_)
        domains_toImport.add(tup)
del sc

#If in the same domain name there are two or more different 'type's:
#add an error about it and abort tool.
names = [tup[0] for tup in domains_toImport]
names.sort()
formerName = ''
for name in names:
    if name.upper() == formerName.upper():
        errorMessage = 'Domain type conflict: domain name "%s" has more than one type' % name
        arcpy.AddError(errorMessage)
        raise Exception(errorMessage)
    formerName = name
del name, formerName

#At this point, if no error has been raised, there are no name duplications.
domains_toImport = list(domains_toImport)

#for every domain name from domains_toImport - 
#create a sub-table that contains only it:
message = 'Importing domains...'
arcpy.SetProgressor("step",message,0,len(domains_toImport),1)

for domainName, domainFieldType in domains_toImport:
    message = 'Importing domain: %s' % domainName
    arcpy.SetProgressorLabel(message)
    arcpy.SetProgressorPosition()
    arcpy.AddMessage(message)
    expression = u"{} = '{}'".format(arcpy.AddFieldDelimiters(domains_table, 'name'), domainName)
    exportTable(domains_table, domains_subTable, expression)
    """
    arcpy.ExportTable_conversion(domains_table, domains_subTable, where_clause = expression)
    arcpy.conversion.ExportTable(
        domains_table,
        domains_subTable,
        where_clause = expression
                                )
    """
    
    #Check if domain name exists in workspace:
    domainExists = domainName.upper() in [domain.name.upper() for domain in workspaceDomains]
    if domainExists:
        #This block empties the domain from all its values, IF it is of the same domain type and field type.
        existingDomain = [domain for domain in workspaceDomains if domain.name.upper() == domainName.upper()][0]
        #Check if the domain is of the same domain type and field type:
        if existingDomain.domainType.upper() != 'CODEDVALUE':
            #The existing domain is not coded value:
            errorMessage = 'The domain "%s" already exists in workspace and its type is not "coded value".' % existingDomain.name
            arcpy.AddError(errorMessage)
        elif existingDomain.type.upper() != domainFieldType.upper():
            #The existing domain is of other field type:
            errorMessage = 'The domain "%s" already exists in workspace and has a different field type.' % existingDomain.name
            arcpy.AddError(errorMessage)
        else:
            #Existing domain is eligible to be modified:
            #Delete ALL its coded values before adding them according to the excel.
            arcpy.AddMessage('Emptying existing domain values.')
            for code in existingDomain.codedValues.keys():
                arcpy.management.DeleteCodedValueFromDomain(input_workspace, domainName, code)
    else:
        #Create a new empty domain
        arcpy.AddMessage('Creating new domain.')
        arcpy.management.CreateDomain(input_workspace,
                                      domainName,
                                      'description',
                                      field_type = domainFieldType,
                                      domain_type = 'CODED'
                                      )
        

    #At this point the workspace has an empty domain, just waiting to be given exciting values!
    sc = arcpy.da.SearchCursor(domains_subTable, ['code', 'description'])
    for code, description in sc:
        arcpy.AddMessage('adding values: {%s: %s}' % (code, description))
        arcpy.management.AddCodedValueToDomain(input_workspace, domainName, code, description)
    del sc

    #@@@@@@@@@@@@@@@@@
    """
    arcpy.management.TableToDomain(
        domains_subTable,
        'code', 'description',
        input_workspace,
        domainName,
        update_option = 'REPLACE'
    )
    """

#delete the last domain table:
message = 'Deleting temporary tables...'
arcpy.SetProgressor("default",message)
arcpy.management.Delete(domains_table)
if arcpy.Exists(domains_subTable):
    arcpy.management.Delete(domains_subTable)

print('done')