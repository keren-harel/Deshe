# -*- coding: utf-8 -*-
import os
import arcpy

arcpy.env.overwriteOutput = True

debug_mode = False
if debug_mode:
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\אוגוסט 2022\QA\smy_form1_180123.gdb'
    input_excelPath = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\אוגוסט 2022\QA\eexxcceell.xlsx'
    temp_table = arcpy.CreateTable_management(input_workspace, 'domainsTable')
else:
    input_workspace = arcpy.GetParameter(0)
    #If provided something other than a proper workspace - try to find its workspace:
    if arcpy.Describe(input_workspace).dataType != 'Workspace':
        itsWorkspace = arcpy.Describe(input_workspace).path
        if arcpy.Describe(itsWorkspace).dataType == 'Workspace':
            #workspace found - overwrite input
            input_workspace = itsWorkspace
        else:
            errorMessage = 'Workspace not found: %' % input_workspace
            arcpy.AddError(errorMessage)
    input_excelPath = arcpy.GetParameterAsText(1)
    temp_table = arcpy.CreateTable_management('in_memory', 'domainsTable')

arcpy.env.workspace = input_workspace

class SmallField_reduced:
    """
    An object with easy access to field details.
    *This is the reduced version that holds less attributes.
    """
    def __init__(self, name, type, length = None):
        self.name = name
        self.alias = self.name
        self.type = type
        self.length = length

        self.isValid = self.validate()

    def validate(self):
        """
        Valdates small field is eligable.
        Returns Boolean.
        """
        unicode_space = '\xa0'
        if (unicode_space in self.name) or (' ' in self.name):
            return False
        else:
            return True

    def __repr__(self):
        return "SmallField object: %s" % self.name

fields = [
    SmallField_reduced('name', 'String'),
    SmallField_reduced('type', 'String'),
    SmallField_reduced('applyToDatabase', 'SmallInteger'),
    SmallField_reduced('code', 'String'),
    SmallField_reduced('description', 'String'),
]

#applyToDatabase is the fields in the output table that directs
#if the domain will be applied to the target database (1) or not (0).
applyToDatabase_default = 0

#create fields in temptable:
for smallfield in fields:
    arcpy.management.AddField(temp_table, smallfield.name, smallfield.type)

#list domains
domains = arcpy.da.ListDomains(input_workspace)
codedValue_domains = [domain for domain in domains if domain.domainType == 'CodedValue']

#start insert cursor:
fieldNames = [smallfield.name for smallfield in fields]
ic = arcpy.da.InsertCursor(temp_table, fieldNames)

message = 'Writing to temporary table...'
arcpy.SetProgressor("step",message,0,len(codedValue_domains),1)

for domain in codedValue_domains:
    name = domain.name
    type_ = domain.type
    message = 'Domain name: %s' % name
    arcpy.SetProgressorLabel(message)
    arcpy.SetProgressorPosition()
    arcpy.AddMessage(message)
    for code, description in domain.codedValues.items():
        ic.insertRow([name, type_, applyToDatabase_default, code, description])
        arcpy.AddMessage('~~~code: %s, description:%s' % (code, description))
    arcpy.AddMessage('--------------------------------------')
del ic
arcpy.ResetProgressor()

message = 'Exporting to excel...'
arcpy.SetProgressor("default",message)

#table to excel:
arcpy.conversion.TableToExcel(temp_table, input_excelPath)

#pass excel path as tool output (derive)
#arcpy.SetParameterAsText(2, input_excelPath)

#delete temptable
arcpy.management.Delete(temp_table)

#open the excel file:
os.startfile(input_excelPath)