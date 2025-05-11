# -*- coding: utf-8 -*-
import os, arcpy, datetime

#VARIABLES
#input_FC = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\נובמבר 2021\november 21\Default.gdb\Semi_replica'
input_FC = arcpy.GetParameter(0)
input_FC = arcpy.Describe(input_FC).catalogPath
#currentYear
nY = datetime.datetime.now().year
plantingYear_fieldName = 'START_YEAR'
fields = {"ageCategory": {"name" : "ageCategory",
                         "alias" : "קבוצת גיל",
                         "type" : "TEXT",
                         "length" : "120"}}

section122_backwards = [
	(1, 'בהקמה (1)'),
    (2, 'בהקמה (2)'),
    (3, 'בהקמה (3)'),
    (4, 'בהקמה (4)'),
    (5, 'בהקמה (5)'),
    (10, 'חדש (6-10)'),
    (15, 'צעיר (11-15)'),
    (20, 'צעיר (16-20)'),
    (25, 'מתבגר (21-25)'),
    (30, 'מתבגר (26-30)'),
    (40, 'בוגר (31-40)'),
    (50, 'בוגר (41-50)'),
    (60, 'בוגר (51-60)'),
    (75, 'ותיק (61-75)'),
    (90, 'ותיק (76-90)'),
    (105, 'ותיק (91-105)'),
    (120, 'ותיק (106-120)')]
section122_defaultValue = None


#FUNCTIONS
def createBlankField(FC, fieldDict):
    FC_desc = arcpy.Describe(FC)
    FC_fieldNames = [x.name for x in FC_desc.fields]
    if fieldDict["name"] in FC_fieldNames:
        arcpy.management.DeleteField(FC, fieldDict["name"])
    arcpy.management.AddField(FC,
                              fieldDict["name"],
                              fieldDict["type"],
                              field_length = fieldDict["length"],
                              field_alias = fieldDict["alias"])
def zto1 (nu):
	return nu + int(nu==0)
def fieldExists(fc, fieldName):
    lstFields = arcpy.ListFields(fc)
    fieldNames = [x.name for x in lstFields]
    return fieldName in fieldNames
def isIntable(x):
    #checks if x can be converted to intteger
    try:
        int(x)
        return True
    except:
        return False
def toCategory(val, backwardsList, defaultValue):
    #val - the value which we want to categorize
    #backwardsList - a list of tuples (maxVal of category, category name)
    if val is None:
        return defaultValue
    for threshold, categoryName in backwardsList:
        if val <= threshold:
            return categoryName

    return defaultValue

#PROCESS
if not fieldExists(input_FC, plantingYear_fieldName):
    arcpy.AddError("Field does't exist:\n-field name: %s" % plantingYear_fieldName)
createBlankField(input_FC, fields["ageCategory"])
uc = arcpy.UpdateCursor(input_FC)

for r in uc:
    plantingYear = r.getValue(plantingYear_fieldName)
    if not isIntable(plantingYear):
        continue
    pY = int(plantingYear)
    #subt = zto1(nY - pY)
    subt = nY - pY + 1
    cat = toCategory(subt, section122_backwards, section122_defaultValue)
    r.setValue(fields["ageCategory"]["name"], cat)
    uc.updateRow(r)
del uc



























#
