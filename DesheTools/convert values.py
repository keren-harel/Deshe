# -*- coding: utf-8 -*-
#CONVERT VALUES VERSION 08.2024
import os
import arcpy
import json
import math

import arcpy.management



#TOOL PARAMETERS
debug_mode = False
if debug_mode:
    #debug parameters
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\QA\29.7.2024\smy_NahalTut_BKP_22062024.gdb'
    input_table = os.path.join(input_workspace, 'smy_NahalTut_1')
    input_configurationFolder = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\עבודה\configuration'
    input_tableQuery = 'points'
else:
    input_table = arcpy.GetParameterAsText(0)
    """
    #Take all the features, even if layar has selection.
    input_table = arcpy.Describe(input_table).catalogPath
    """
    input_configurationFolder = arcpy.GetParameterAsText(1)
    input_tableQuery = arcpy.GetParameterAsText(2)

#VARIABLES
fieldsExcel = os.path.join(input_configurationFolder, 'fields.xlsx')
fieldsExcel_fields_sheet = 'fields'
fieldsExcel_convertValues_sheet = 'convert values'

conversionExcel_queryFieldName = 'target'


#FUNCTIONS

def fieldsExcelToDict(excelPath, sheet):
    """
    excelPath <str>, sheet <str>.
    Takes an Excel file containing fields codes and info
    and returns a dictionary as follows:
    {field code <int>: {name: "", alias:, "", type: "", domain: "", checkIfExists: None/1, order: <int>, toAdd: 'keepValues'/'blank'/'' (<string>)}
    """
    #Notify in UI about process start:
    message = 'Importing fields: %s' % os.path.basename(excelPath)
    arcpy.SetProgressor('default', message)
    arcpy.AddMessage(message)

    tempTableName = os.path.join("in_memory", "fieldsTable")
    arcpy.ExcelToTable_conversion(excelPath, tempTableName, Sheet=sheet)
    #check all the following fields exist in tempTable:
    fieldNames = [field.name.lower() for field in arcpy.Describe(tempTableName).fields]
    for fieldName in ["code", "name", "alias", "type", "domain", "length"]:
        if fieldName.lower() not in fieldNames:
            arcpy.AddError('Field "%s" does not exist in fields-excel:\n%s' % (fieldName, excelPath))
    #Create the outputDict and insert data:
    outputDict = {}
    #Add a useful attribute:
    outputDict['__excelFileName__'] = os.path.basename(excelPath)
    fieldsExcelToDict_sc = arcpy.SearchCursor(tempTableName)
    for fieldsExcelToDict_r in fieldsExcelToDict_sc:
        code = fieldsExcelToDict_r.getValue('code')
        #Warn in case code is overwriting:
        if code in outputDict.keys():
            arcpy.AddWarning('Field code (%s) appers more than once in "%s".' % (code, outputDict['__excelFileName__']))
        fieldObj = SmallField(
            code,
            fieldsExcelToDict_r.getValue('name'),
            fieldsExcelToDict_r.getValue('alias'),
            fieldsExcelToDict_r.getValue('type'),
            fieldsExcelToDict_r.getValue('domain'),
            fieldsExcelToDict_r.getValue('length'),
        )
        #outputDict[code] = {'name': name, 'alias': alias, 'type': type, 'domain': domain, checkIfExists: 0/1, sequence: ,<int>}}
        outputDict[code] = fieldObj
    del fieldsExcelToDict_sc
    arcpy.management.Delete(tempTableName)
    return outputDict

def removeDup(array):
    #returns a list w/o duplications.
    return list(set(array))

def buildSqlQuery(featureClass, fieldName, value, mode = "="):
    """
    Takes:
       featureClass = featureClass path.
       fieldName = field name to search in.
       value = the value to which the WHERE clause will be equal to.
    Returns:
       sql expression of "fieldName EQUALS value".
    """
    featureClass_workspace = os.path.dirname(arcpy.Describe(featureClass).catalogPath)
    fieldName_delimited = arcpy.AddFieldDelimiters(featureClass_workspace, fieldName)
    if mode in ("=", "<>"):
        return """{0} {1} '{2}'""".format(fieldName_delimited, mode, value)
    elif mode in ("= timestamp", "<> timestamp"):
        return """{0} {1} '{2}'""".format(fieldName_delimited, mode, value)
    else:
        return ""

def buildSqlQuery_relationship(ralationship, value, mode = "="):
    #takes:
    #   ralationship = RelationshipClass object.
    #   value = the value to which the WHERE clause will be equal to.
    ralationship_workspace = ralationship.workspace
    foreignKey_field = ralationship.foreignKey_fieldName
    foreignKey_field_delimited = arcpy.AddFieldDelimiters(ralationship_workspace, foreignKey_field)
    if mode in ("=", "<>"):
        return """{0} {1} '{2}'""".format(foreignKey_field_delimited, mode, value)
    elif mode in ("= timestamp", "<> timestamp"):
        return """{0} {1} '{2}'""".format(foreignKey_field_delimited, mode, value)
    else:
        return ""

def getOidFieldName(fc):
    #returns the Objectid field of a fc.
    fc_desc = arcpy.Describe(fc)
    oidFieldName = fc_desc.oidFieldName
    del fc_desc
    return oidFieldName

def getFeatureCount(feature):
    return int(arcpy.management.GetCount(feature)[0])

def checkValueType(value):
    if isinstance(value, (int, float)):
        return "Numerical"
    elif isinstance(value, str):
        return "String"
    else:
        return "Other"

def is_convertible_to_number(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def toNumber(value):
    """
    Takes a numerical-convertable value and converts it into a number.
    """
    try:
        # Try to convert to an integer
        return int(value)
    except ValueError:
        try:
            # Try to convert to a float
            return float(value)
        except ValueError:
            # Return None if conversion is not possible
            return None



#CLASSES
class SmallField:
    """
    An object with easy access to field details.
    """
    def __init__(self, code, name, alias, type, domain, length = None):
        self.code = code
        self.name = name
        self.alias = alias
        self.type = type
        self.domain = domain
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
        return "SmallField object: %s, %s, %s" % (self.code, self.name, self.alias)
    
    def asText(self):
        return "\t-code: %s, name: %s, alias: %s" % (self.code, self.name, self.alias)

class ConversionMatrixCoordinator:
    #An object that initializes and deals with conversion matrices.
    def __init__(self, xlPath, sheet):
        #ATTENTION!
        #in order for this matrix to be consistent with the exact same
        #strings provided in the excel table, always use field's ALIAS name.

        #Notify in UI about process start:
        message = 'Creatung matrix object: %s' % os.path.basename(xlPath)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)

        overwrite_original = arcpy.env.overwriteOutput
        arcpy.env.overwriteOutput = True
        #tblPath = os.path.join(arcpy.env.scratchGDB,"matrix")
        tblPath = os.path.join(arcpy.env.workspace,"matrix")
        arcpy.ExcelToTable_conversion(xlPath, tblPath, Sheet=sheet)

        #Notify in UI about table dimensions:
        Ncol = len(arcpy.Describe(tblPath).fields)
        Nrow = getFeatureCount(tblPath)
        message = 'Creating matrix object: %s. Table dimensions: %sx%s' % (os.path.basename(xlPath), Ncol, Nrow)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)
        
        #This is the dict to be constructed in this __init__() method
        #and be availabe for use later:
        #{fieldCode: {from: to}, ...}, ...}
        #ATTENTION: possible pitfall!
        #The dictionary is ordered by field-CODES,
        #while the cursor search with the field-NAME.
        #So pay attention to field name ambiguity.
        self.coordinationDict = {}
        self.basename = os.path.basename(xlPath)
        
        fields = ['code', 'findWhat', 'replaceWith']
        
        #rows will be counted in the sc iteration:
        rows_N = 0

        #Construct self.coordinationDict using cursor:
        sqlQuery = buildSqlQuery(tblPath, conversionExcel_queryFieldName, input_tableQuery)
        sc = arcpy.da.SearchCursor(tblPath, fields, where_clause = sqlQuery)
        for r in sc:
            rows_N += 1
            try:
                code = r[0]
                fieldCode = int(code)
            except ValueError:
                txt = f'Could not turn code "{code}" to integer. Check {self.basename}.'
                arcpy.AddError(txt)
            #Checks if the code provided in the conversion table appears in field codes excel:
            #if it does not - notily and continue, e.g, don't use it.
            if fieldCode not in fieldsDict.keys():
                excelFileName = fieldsDict['__excelFileName__']
                txt = f'Field "{fieldCode}" from {self.basename} does not appear in {excelFileName}.'
                arcpy.AddError(txt)
                continue

            value_from = r[1]
            value_to = r[2]
            #The default type for all values of value_from and value_to is STRING,
            #even if they represent numbers.
            #If possible, turn them into numbers:
            if is_convertible_to_number(value_from):
                value_from = toNumber(value_from)
            if is_convertible_to_number(value_to):
                value_to = toNumber(value_to)
            
            if fieldCode not in self.coordinationDict.keys():
                #This is the first time the field code appears.
                self.coordinationDict[fieldCode] = {value_from: value_to}
            elif value_from in self.coordinationDict[fieldCode].keys():
                #Value_from already exists and logic would not know which value
                #to choose. Raise a warning and don't take the values.
                txt = f"Find value (value_from{value_from}) appears more than once and won't be used. code: {code}, file: {self.basename}."
                arcpy.AddWarning(txt)
                continue
            else:
                #Code already appeared, and now it has a different value_from.
                self.coordinationDict[fieldCode][value_from] = value_to
        del sc, sqlQuery

        #self.inputOptions~ is a list of possible keys:
        self.fieldCodes = list(self.coordinationDict.keys())
        self.fieldNames = [fieldsDict[code].name for code in self.fieldCodes]


        arcpy.env.overwriteOutput = overwrite_original
        arcpy.Delete_management(tblPath)
        arcpy.ResetProgressor()

    def solve(self, rawValue, fieldCode):
        """
        Takes a raw value from a field and see if it has the value/s
        we want to replace, replaces it and returns converted value.
        """
        output = {
            'count': 0,
            'value': rawValue
        }
        valueType = checkValueType(rawValue)
        conversionDict = self.coordinationDict[fieldCode]
        if valueType == "String":
            """
            String type values are asked to be split by commas,
            each separate value is inspected for replacements,
            in the end all values are joined again with commas.
            """
            values_split = values_split = rawValue.split(",")
            replaced_results = [self.replaceStr(splitVal, conversionDict) for splitVal in values_split]
            replaced_values = [v['output'] for v in replaced_results]
            values_join = ",".join(replaced_values)
            replace_count = sum([v['status'] == 'replaced' for v in replaced_results])
            output['count'] = replace_count
            output['value'] = values_join
            return output
        elif valueType == "Numerical":
            """
            Numerical type is being checked for replacement and returnd accordingly.
            """
            replaced_result = self.replaceNum(rawValue, conversionDict)
            if replaced_result['status'] == 'replaced':
                output['count'] = 1
                output['value'] = replaced_result['output']
            return output
        else:
            #Value type is not a String nor a Numerical, return the raw value.
            return output

    def getFroms(self, fieldCode):
        """
        Takes a fieldCode and returns a list of all its "from" values.
        If fieldCode does not appear in conversion table - return empty list.
        """
        if fieldCode in self.coordinationDict.keys():
            return list(self.coordinationDict[fieldCode].keys())
        else:
            return []
    
    def replaceStr(self, input_value, conversionDict):
        """
        Takes an input value of the type string,
        checks if INPUT VALUE contains a string from conversionDict keys.
        If it does - replace and return.
        NOTICE: applies only for the FIRST match.
        #Inputs:
        - input_value <str>: the value under inspection.
        - conversionDict <dict>: {{value_from: value_to}, {}...}.
        #Output:
        - <dict> with two attributes:
            'status' replaced or not replaced,
            'output: it replaced: the replaced value; if not: the input_value.
        """
        for value_from, value_to in conversionDict.items():
            #Since this method deals with strings, in case the from-and-to were
            #saved as numbers, we should turn them into strings.
            value_from = str(value_from)
            value_to = str(value_to)
            if value_from in input_value:
                replaced_value = input_value.replace(value_from, value_to)
                output = {
                    'status': 'replaced',
                    'output': replaced_value
                }
                return output
        #If no substitue was found: return empty.
        output = {
                    'status': 'not replaced',
                    'output': input_value
                }
        return output
    
    def replaceNum(self, input_value, conversionDict):
        """
        Takes an input value of the type int / float,
        checks if is equal to any of the keys in conversionDict.
        If it does - replace and return.
        NOTICE: applies only for the FIRST match.
        #Inputs:
        - input_value <int/float>: the value under inspection.
        - conversionDict <dict>: {{value_from: value_to}, {}...}.
        #Output:
        - <dict> with two attributes:
            'status' replaced or not replaced,
            'output: it replaced: the replaced value; if not: the input_value.
        """
        for value_from, value_to in conversionDict.items():
            if value_from == input_value:
                replaced_value = value_to
                output = {
                    'status': 'replaced',
                    'output': replaced_value
                }
                return output
        #If no substitue was found: return empty.
        output = {
                    'status': 'not replaced',
                    'output': input_value
                }
        return output
    

#PROCESS
arcpy.env.overwriteOutput = True
arcpy.env.workspace = arcpy.Describe(input_table).path

fieldsDict = fieldsExcelToDict(fieldsExcel, fieldsExcel_fields_sheet)
#Validate fieldsDict, notify if needed:
invalidFields = []
for smallFieldObj in fieldsDict.values():
    if hasattr(smallFieldObj, 'isValid'):
        if not smallFieldObj.isValid:
            invalidFields.append(smallFieldObj)
if invalidFields:
    warning = 'The following fields are invalid:'
    arcpy.AddWarning(warning)
    for invalidField in invalidFields:
        warning = "\t~> %s : %s" % (invalidField.code, invalidField.name)
        arcpy.AddWarning(warning)
    errorText = 'Please fix these fields and run again.'
    arcpy.AddError(errorText)


#create matrices:
conversionCoordinator = ConversionMatrixCoordinator(fieldsExcel, fieldsExcel_convertValues_sheet)

#Find only the fields that appear in the input_table.
input_table_fieldNames = [f.name.upper() for f in arcpy.ListFields(input_table)]
fieldCodes = []
fieldNames = []
for fieldCode in conversionCoordinator.fieldCodes:
    fieldName = fieldsDict[fieldCode].name
    if fieldName in fieldNames:
        #For cases when to different codes represent the same name.
        continue
    if fieldName.upper() in input_table_fieldNames:
        fieldCodes.append(fieldCode)
        fieldNames.append(fieldName)

#Get the objectid field name and use it LAST in fields order,
#for debugging and reference.
input_table_oidFieldName = getOidFieldName(input_table)

#### Process section 1: ####
# Go through each row:

if fieldNames:
    #Notify in UI about process start:
    message = 'Calculating...'
    featureCount = getFeatureCount(input_table)
    arcpy.SetProgressor("step",message,0,featureCount,1)
    arcpy.AddMessage(message)
    counter = 1

    uc = arcpy.UpdateCursor(input_table)
    #Main iteration:
    for r in uc:
        tempMessage = 'Calculating... (row: %s of %s feafures)' % (counter, featureCount)
        arcpy.SetProgressorLabel(tempMessage)

        conversionResults = []
        conversionsMade = 0
        rowOid = r.getValue(input_table_oidFieldName)
        arcpy.AddMessage('Started calculating: %s = %s'% (input_table_oidFieldName, rowOid))
        for i, fieldName in enumerate(fieldNames):
            #iterate through each value in the row, except objectID.
            fieldCode = fieldCodes[i]
            rawValue = r.getValue(fieldName)
            conversionResult = conversionCoordinator.solve(rawValue, fieldCode)
            conversionMade = conversionResult['count'] > 0
            if conversionMade:
                #update results: value and count:
                r.setValue(fieldName, conversionResult['value'])
                conversionsMade += conversionResult['count']
        arcpy.AddMessage('\t-Done row. Conversions made: %s.' % conversionsMade)
        #When finished all fields, update the row:
        uc.updateRow(r)

        arcpy.SetProgressorPosition()
        counter += 1
    del uc
else:
    #No field names: field codes provided in the excel table do not
    #have a matching field name in the input_table.
    txt = f'Fields from {conversionCoordinator.basename} could not be found in {os.path.basename(input_table)}.\
 No change was made.'
    arcpy.AddError(txt)

print('done')