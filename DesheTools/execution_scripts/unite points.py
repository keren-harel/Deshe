# -*- coding: utf-8 -*-
import os
import arcpy
import json
import math
import datetime
from collections import Counter

#TOOL PARAMETERS
debug_mode = False
addFields = True
if debug_mode:
    #debug parameters
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\QA\2025.10.16\smy_survey_Galed_BKP_070125_before_Unitestands.gdb'
    input_stands = os.path.join(input_workspace, 'stands_3402_fnl')
    input_sekerpoints = os.path.join(input_workspace, 'smy_survey_Galed')
    #input_configurationFolder = r'INSERT CUSTOM PATH HERE'
    input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')
    input_beitGidul = "ים-תיכוני"
else:
    input_stands = arcpy.GetParameter(0)
    #Take all the features, even if layar has selection.
    input_stands = arcpy.Describe(input_stands).catalogPath

    input_sekerpoints = arcpy.GetParameter(1)
    #Take all the features, even if layar has selection.
    input_sekerpoints = arcpy.Describe(input_sekerpoints).catalogPath

    #input_configurationFolder = arcpy.GetParameterAsText(2)
    input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')

    input_beitGidul = arcpy.GetParameterAsText(2)


#VARIABLES
fieldsExcel = os.path.join(input_configurationFolder, 'fields.xlsx')
fieldsExcel_sheet = 'unite points'
#speciesExcel = os.path.join(input_configurationFolder, 'speciesPlantsCodeNames.xlsx')
forestVegFormExcel = os.path.join(input_configurationFolder, 'ForestVegForm.xlsx')
standVegFormExcel = os.path.join(input_configurationFolder, 'StandVegForm.xlsx')
speciesCompositionExcel = os.path.join(input_configurationFolder, 'species composition.xlsx')
relativeDensityKeyExcel = os.path.join(input_configurationFolder, 'relativeDensityKey.xlsx')
totalCoverageExcel = os.path.join(input_configurationFolder, 'TotalCoverage.xlsx')
#GDB that contains all the domains needed.
origin_GDB = os.path.join(input_configurationFolder, 'origin.gdb')
origin_GDB_domains = arcpy.Describe(origin_GDB).domains
#Import JSON file
speciesHierarchy_path = os.path.join(input_configurationFolder, 'speciesHierarchy.json')
with open(speciesHierarchy_path, encoding='utf-8') as f:
    speciesHierarchy_jsonObject = json.load(f)

sekerpoints_tables_relationships = {
    #'nickname': ('name of relationship class', field codes prefix <int>),
    'pt1': (os.path.basename(input_sekerpoints) + '_InvasiveSpecies', 41),
    'pt2': (os.path.basename(input_sekerpoints) + '_PlantTypeCoverDistribut', 42),
    'pt3': (os.path.basename(input_sekerpoints) + '_StartRepeatDominTree', 43),
    'pt4': (os.path.basename(input_sekerpoints) + '_VitalForest', 44),
}
stands_relatedTables = {
    "st1": {
        "name": "InvasiveSpecies",
        "fieldCodes": [51001,51002]
    },
    "st2": {
        "name": "PlantTypeCoverDistribut",
        "fieldCodes": [52001,52002]
    },
    "st3": {
        "name": "StartRepeatDominTree",
        "fieldCodes": [53001,53002]
    },
    "st4": {
        "name": "VitalForest",
        "fieldCodes": [54001,54002]
    },
}
#Fields to be added to each related table
#the first one is ALWAYS used for linkage in relationship class!
#the order of the other codes matters as well.
#[stand_ID, standAddress, FOR_NO, HELKA, STAND_NO]
stands_relatedTables_globalFieldCodes = [59001,59002,59003,59004,59005]

#A field to be added to seker points feature class,
# to relate it with stands.
standID_field = {
    "inputField": "globalid",
    "name": "stand_ID",
    "aliasName": "stand_ID",
    "type": "Guid",
    'isNullable': True
}

forestAddressFieldNames = ["FOR_NO", "HELKA", "STAND_NO"]
#forestAddressFieldCodes = [40006, ] - HARD-CODED FOR NOW


layerToShortText = {
    4: "tmira",
    3: "high",
    2: "mid",
    1: "sub"
}

layerToLongText = {
    4: "תמירה",
    3: "גבוהה",
    2: "בינונית",
    1: "קומת קרקע"
}

layerToLongText_m = {
    #Hebrew male form.
    4: "תמיר",
    3: "גבוה",
    2: "בינוני",
    1: "קומת קרקע"
}

longTextToLayer = {
    "תמירה": 4,
    "גבוהה": 3,
    "בינונית": 2,
    "קומת קרקע": 1
}

layerCover_table1 = {
            #value <str>: (ordered num <int>, ceil of avg <int>, max <int>),
            "אין": (0, 0, 0),
            "זניח (3%-0%)": (1, 2, 3),
            "פזור (10%-3%)": (2, 7, 10),
            "פתוח (33%-10%)": (3, 22, 33),
            "בינוני (66%-33%)": (4, 50, 66),
            "גבוה (מעל 66%)": (5, 88, 100),
        }
layerCover_table1_backwardsList = [(v[2],k) for k,v in layerCover_table1.items()]

subForestVegForm_translation = {
    #based on instructions from February 2023.
    "שיחים": "שיחייה",
    "בני_שיח": "בתה",
    "בני שיח": "בתה",
    "צומח_גדות_נחלים": "צומח גדות נחלים",
    "בוסתנים_ומטעים": "בוסתנים ומטעים",
    "שיטים_פולשני": "שיטים פולשני",
    "יער_גדות_נחלים": "יער גדות נחלים",
    "ללא_כיסוי": "ללא כיסוי",
}

beitgidulList = [
    "ים-תיכוני",
    "ים-תיכוני יבש",
    "צחיח-למחצה"
]

#FUNCTIONS
def importDomain(domainName, sourceGDB, destinationGDB):
    """
    Checks if a domain exists in source GDB and imports it to destination GDB.
    """
    source_domains = arcpy.Describe(sourceGDB).domains
    destination_domains = arcpy.Describe(destinationGDB).domains
    if not domainName in source_domains:
        #If the desired domain is not in source GDB → warn, don't add it, continue and CREATE FIELD w/o domain.
        arcpy.addWarning('Could not import domain "%s", from GDB: "%s". Field will be created without assigning this domain.' % (domainName, sourceGDB))
        return
    elif not domainName in destination_domains:
        #Domain exists in source and not in destination → export it as a table to scratch GDB → import it to destination GDB.
        tempDomainTable = os.path.join(arcpy.env.scratchGDB, "tempDomainTable")
        arcpy.management.DomainToTable(sourceGDB, domainName, tempDomainTable, "code_field", "description_field")
        arcpy.management.TableToDomain(tempDomainTable, "code_field", "description_field", destinationGDB, domainName)
        arcpy.management.Delete(tempDomainTable)
    else:
        #That's a bug, should not get here and requires a look...
        arcpy.AddError('Error importing domain: %s. Check domains of origin and destination GDB.' % domainName)

def createRelation(originFC, originKey, destinationFC, destinationKey):
        """
        A function that creates a new relationship class.
        return relationship describe object
        originFC, destinationFC - featureclass objects.
        originKey, destinationKey - field names (string).
        """

        #Check that originFC, destinationFC are in the same workspace (e.g, same GDB).
        if originFC.workspace != destinationFC.workspace:
            arcpy.AddError('Error during attepmt to create a relationship class.\n\
Features are not in the same GDB:\n' + '\n'.join([originFC.fullPath, destinationFC.fullPath]))
        
        #Check if a relationship class of the same name already exists,
        #if it does - don't create a new one, and just assign it to the origin and destination FCs.
        relationship_name = "_".join([originFC.name, destinationFC.name])
        relationship_fullPath = os.path.join(arcpy.env.workspace, relationship_name)
        if arcpy.Exists(relationship_fullPath):
            relDesc = arcpy.Describe(relationship_fullPath)
            isRelClass = relDesc.dataType == 'RelationshipClass'
            if isRelClass:
                arcpy.AddMessage('Relationship "%s" already exists.' % relationship_name)
                #Check if origin, destination and keys are identical.
                #If they are not - overwrite.
                conditions = [
                    originFC.name.lower() == relDesc.originClassNames[0].lower(),
                    destinationFC.name.lower() == relDesc.destinationClassNames[0].lower(),
                    originKey.lower() == relDesc.originClassKeys[0][0].lower(),
                    destinationKey.lower() == relDesc.originClassKeys[1][0].lower(),
                    'OneToMany'.lower() == relDesc.cardinality.lower(),
                ]
                isIdentical = False not in conditions
                if isIdentical:
                    return relDesc
                else:
                    #The existing relationship class is not identical, create a new
                    #one (overwrite it).
                    createRelationship_result = arcpy.management.CreateRelationshipClass(originFC.name, destinationFC.name, relationship_name, "SIMPLE", destinationFC.name, originFC.name, "NONE", "ONE_TO_MANY", "NONE", originKey, destinationKey, '', '')
                    relDesc = arcpy.Describe(createRelationship_result)
            else:
                arcpy.AddError('Error during attepmt to create a relationship class.\n\
Name is already taken: \n' + relationship_fullPath)
        else:
            createRelationship_result = arcpy.management.CreateRelationshipClass(originFC.name, destinationFC.name, relationship_name, "SIMPLE", destinationFC.name, originFC.name, "NONE", "ONE_TO_MANY", "NONE", originKey, destinationKey, '', '')
            relDesc = arcpy.Describe(createRelationship_result)
            return relDesc

def createBlankField(FC, smallFieldObj):
    FC_desc = FC.desc
    FC_fieldNames = [x.name for x in FC_desc.fields]
    #if field already exists: delete it.
    if smallFieldObj.name.upper() in [x.upper() for x in FC_fieldNames]:
        arcpy.management.DeleteField(FC.fullPath, smallFieldObj.name)
    #if field has domain: make sure it exists in FC workspace,
    #and if not - import it.
    if (smallFieldObj.domain) and (smallFieldObj.domain not in FC.wsDomains):
        arcpy.AddMessage('Importing domain: ' + smallFieldObj.domain)
        importDomain(
            smallFieldObj.domain,
            origin_GDB,
            FC.workspace
        )
    #create field:
    if smallFieldObj.length:
        return arcpy.management.AddField(
            FC.fullPath,
            smallFieldObj.name,
            smallFieldObj.type,
            field_length = smallFieldObj.length,
            field_alias = smallFieldObj.alias,
            field_domain = smallFieldObj.domain
            )
    else:
        return arcpy.management.AddField(
            FC.fullPath,
            smallFieldObj.name,
            smallFieldObj.type,
            field_alias = smallFieldObj.alias,
            field_domain = smallFieldObj.domain
            )

def moveFieldToEnd(FC, targetField, referenceField):
    """
    Takes a field that already exists and re-creates it in the last
    position in the same feature class, conserving its values.
    -FC: the FC on which the function runs.
    -targetField: smallfield object of the field to be moved.
    -referenceField: smallfield object of the field upoun which
                     the join will be based.
    """
    FC_fieldnames = [field.name.lower() for field in FC.desc.fields]

    fieldExists = targetField.name.lower() in FC_fieldnames
    if fieldExists:
        #1)Table to table:
        #create field mappings:
        fms = arcpy.FieldMappings()

        #reference field:
        fm_r = arcpy.FieldMap()
        #check if field exists:
        if referenceField.name.lower() not in FC_fieldnames:
            #field won't be found, so post an ERROR:
            errorMessage = 'Could not move field. Table: %s does not have field: %s'\
            % (FC.name, referenceField.name)
            arcpy.AddError(errorMessage)
            return
        fm_r.addInputField(FC.fullPath, referenceField.name)
        #if the reference field is of 'globalid' type:
        #→change it into String.
        if fm_r.outputField.type.lower() == 'globalid':
            outField = fm_r.outputField
            outField.type = 'String'
            fm_r.outputField = outField
            del outField
        
        #target field:
        fm_t = arcpy.FieldMap()
        #check if field exists:
        if targetField.name.lower() not in FC_fieldnames:
            #field won't be found, so post an ERROR:
            errorMessage = 'Could not move field. Table: %s does not have field: %s'\
            % (FC.name, targetField.name)
            arcpy.AddError(errorMessage)
            return
        fm_t.addInputField(FC.fullPath, targetField.name)
        #alias name must be set specifically:
        outField = fm_t.outputField
        outField.aliasName = targetField.alias
        fm_t.outputField = outField
        del outField

        fms.addFieldMap(fm_r)
        fms.addFieldMap(fm_t)

        arcpy.TableToTable_conversion(
            FC.fullPath,
            'in_memory',
            'temp',
            field_mapping = fms
        )
        temptable = os.path.join('in_memory', 'temp')

        arcpy.management.DeleteField(FC.fullPath, targetField.name)

        arcpy.management.JoinField(
            in_data= FC.fullPath,
            in_field= referenceField.name,
            join_table= temptable,
            join_field= referenceField.name,
            fields= targetField.name,
            fm_option= "NOT_USE_FM",
            field_mapping= None
        )

        arcpy.management.Delete(temptable)
        return
    
    else:
        #The field does not exist, create it blank:
        createBlankField(FC, targetField)
        return

def importField(fromFC, toFC, fieldName):
    """
    Takes a field of 'fieldName' from 'fromFC' and creates it in 'toFC'.
    - fromFC, toFC: FeatureClass objects.
    - fieldName: string.
    """
    arcpy.AddMessage("Transferring field %s from %s to %s." % (fieldName, fromFC, toFC))
    fromFieldList = fromFC.desc.fields
    fieldAdded = False
    for field in fromFieldList:
        if field.name.lower() == fieldName.lower():
            #That's the field.
            #handle its domain if exists:
            if field.domain:
                if not field.domain in toFC.wsDomains:
                    arcpy.AddMessage('Importing domain: ' + field.domain)
                    importDomain(field.domain, fromFC.workspace , toFC.workspace)
            
            arcpy.management.AddField(
                toFC.fullPath,
                field.name,
                field.type,
                field.precision,
                field.scale,
                field.length,
                field.aliasName,
                field.isNullable,
                field.required,
                field.domain
            )
            fieldAdded = True
    if not fieldAdded:
        arcpy.AddMessage("Field %s wasn't found in: %s." % (fieldName, fromFC.name))

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
    for fieldName in ["code", "name", "alias", "type", "domain", "length", "checkIfExists", "sequence", "toAdd"]:
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
            fieldsExcelToDict_r.getValue('checkIfExists'),
            fieldsExcelToDict_r.getValue('sequence'),
            fieldsExcelToDict_r.getValue('toAdd'),
            fieldsExcelToDict_r.getValue('length'),
        )
        #outputDict[code] = {'name': name, 'alias': alias, 'type': type, 'domain': domain, checkIfExists: 0/1, sequence: ,<int>}}
        outputDict[code] = fieldObj
    del fieldsExcelToDict_sc
    arcpy.management.Delete(tempTableName)
    return outputDict

def speciesExcelToDict_old(excelPath):
    """
    Takes an Excel file containing species codes and names
    and returns a dictionary as follows:
    {species code <int>: species name <str>, }
    """
    #Notify in UI about process start:
    message = 'Importing species: %s' % os.path.basename(excelPath)
    arcpy.SetProgressor('default', message)
    arcpy.AddMessage(message)

    tempTableName = os.path.join("in_memory", "speciesTable")
    arcpy.ExcelToTable_conversion(excelPath, tempTableName)
    #check all the following fields exist in tempTable:
    fieldNames = [field.name.lower() for field in arcpy.Describe(tempTableName).fields]
    for fieldName in ["sp_code", "sp_name"]:
        if fieldName.lower() not in fieldNames:
            arcpy.AddError('Field "%s" does not exist in fields-excel:\n%s' % (fieldName, excelPath))
    #Create the outputDict and insert data:
    outputDict = {}
    #Add a useful attribute:
    outputDict['__excelFileName__'] = os.path.basename(excelPath)
    fieldsExcelToDict_sc = arcpy.SearchCursor(tempTableName)
    for fieldsExcelToDict_r in fieldsExcelToDict_sc:
        code = fieldsExcelToDict_r.getValue('sp_code')
        name = fieldsExcelToDict_r.getValue('sp_name')
        #Warn in case code is overwriting:
        if code in outputDict.keys():
            arcpy.AddWarning('Species code (%s) appers more than once in "%s".' % (code, outputDict['__excelFileName__']))
        if isIntable(code):
            outputDict[int(code)] = name
        else:
            arcpy.AddWarning('Species code: (%s) cannot be turned to integer. [%s]' % (code, outputDict['__excelFileName__']))
    del fieldsExcelToDict_sc
    arcpy.management.Delete(tempTableName)
    return outputDict

def speciesExcelToDict1_old(excelPath):
    """
    Takes an Excel file containing species codes and names
    and returns a dictionary as follows:
    {species code <int>: {source_name, alt_name, alt_codedValue}, }
    """
    #Notify in UI about process start:
    message = 'Importing species: %s' % os.path.basename(excelPath)
    arcpy.SetProgressor('default', message)
    arcpy.AddMessage(message)

    tempTableName = os.path.join("in_memory", "speciesTable")
    arcpy.ExcelToTable_conversion(excelPath, tempTableName)
    #check all the following fields exist in tempTable:
    fieldNames = [field.name.lower() for field in arcpy.Describe(tempTableName).fields]
    for fieldName in ["sp_code", "sp_name", "sp_domName", "sp_domCode"]:
        if fieldName.lower() not in fieldNames:
            arcpy.AddError('Field "%s" does not exist in fields-excel:\n%s' % (fieldName, excelPath))
    #Create the outputDict and insert data:
    outputDict = {}
    #Add a useful attribute:
    outputDict['__excelFileName__'] = os.path.basename(excelPath)
    fieldsExcelToDict_sc = arcpy.SearchCursor(tempTableName)
    for fieldsExcelToDict_r in fieldsExcelToDict_sc:
        source_codedValue = fieldsExcelToDict_r.getValue('sp_code')
        source_name = fieldsExcelToDict_r.getValue('sp_name')
        alt_name = fieldsExcelToDict_r.getValue('sp_domName')
        alt_codedValue = fieldsExcelToDict_r.getValue('sp_domCode')

        #Warn in case source_codedValue is overwriting:
        if source_codedValue in outputDict.keys():
            arcpy.AddWarning('Species code (%s) appers more than once in "%s".' % (source_codedValue, outputDict['__excelFileName__']))
        if isIntable(source_codedValue):
            outputDict[int(source_codedValue)] = {
                'source_name': source_name,
                'alt_name': alt_name,
                'alt_codedValue': alt_codedValue
            }
        else:
            arcpy.AddWarning('Species code: (%s) cannot be turned to integer. [%s]' % (source_codedValue, outputDict['__excelFileName__']))
    del fieldsExcelToDict_sc
    arcpy.management.Delete(tempTableName)
    return outputDict

def createSpeciesDict(rootNode, jsonPath):
    """
    Takes:
    -rootNode <node Object>
    -JSON file path
    Traces the root node down all its children and
    Returns a dictionary as follows:
    {species code <int>: species name <str>, }
    plus the key-value of:
    '__jsonFileName__': 'NAME_OF_JSONfILE.json'
    """
    outputDict = {}
    outputDict['__jsonFileName__'] = os.path.basename(jsonPath)
    createSpeciesDict_rec(rootNode, outputDict)
    return outputDict

def createSpeciesDict_rec(node, dic):
    """
    An accessory recursive function.
    """
    try:
        code = int(node.codedValue)
        #print(code)
        name = node.name
        dic[code] = name
    except ValueError as e:
        #print (node.codedValue, e)
        pass
    for child in node.children:
        createSpeciesDict_rec(child, dic)

def isIntable(value):
    """
    Checks if the value can be turned into integer.
    """
    try:
        int(value)
        return True
    except:
        return False
    
def average(aList):
    return sum(aList)/len(aList)

def specialDivide(numerator, denominator):
    """
    Takes numerator <int> and denumerator <int>
    returns a list of INTEGERS not necessarily equal
    The sum of them is equal to numerator.
    8,3 → [3,3,2]
    8,4 → [2,2,2,2]
    """
    dividable = numerator%denominator == 0
    if dividable:
        return [int(numerator/denominator)]*denominator
    else:
        ar = [math.floor(numerator/denominator)]*denominator
        index = 0
        while sum(ar)<numerator:
            trueIndex = index % len(ar)
            ar[trueIndex] += 1
            index += 1
        return ar

def toCategory(val, backwardsList, defaultValue = None):
    """
    val - the value which we want to categorize
    backwardsList - a list of tuples (maxVal of category, category name)
    """
    #Give val an upper limit:
    val = min(val, 100)
    for threshold, categoryName in backwardsList:
        if val <= threshold:
            return categoryName
    return defaultValue

def listCodedValues(workspace, domainName):
    #Accessory function for me.
    domains = arcpy.da.ListDomains(workspace)
    codedValuesList = []
    for domain in domains:
        if domain.name == domainName:
            for val, desc in domain.codedValues.items():
                codedValuesList.append(val)
                #print('"%s",' % val)
    return codedValuesList

def freqSorted(inputIterable):
    """
    Returns a sorted version of the list inserted W/O duplications,
    with the most frequent objects appearing first.
    """
    sortedL = sorted(inputIterable, key=Counter(inputIterable).get, reverse=True)
    outL = []
    for x in sortedL:
        if x not in outL:
            outL.append(x)
    return outL

def flatten(input_listOfLists):
    #Takes a list of lists [[1,2,3],[1,2,4],...]
    #and returns a list [1,2,3,1,2,4]
    return [item for sublist in input_listOfLists for item in sublist]

def makeLast(input_list, var):
    """
    Returns the list after the variable moved to end.
    """
    if var in input_list:
        index = input_list.index(var)
        return input_list[:index]+input_list[index+1:]+[var]
    else:
        #Do nothing because the variable is not in the list.
        return input_list

def normal_round(n):
    """
    This is a round function that rounds .5 up.
    [The built-in round() doesn't do it properly].
    """
    if n - math.floor(n) < 0.5:
        return math.floor(n)
    return math.ceil(n)

def listThrough(start,end):
    """
    Prints a copy-able list of ints from start to end (included).
    """
    strList = ["[\n"]
    for i in range(start, end+1):
        strList.append("\t%s,\n"%i)
    strList.append("]")
    concat = ''.join(strList)
    print(concat)

def getFeatureCount(feature):
    return int(arcpy.management.GetCount(feature)[0])

def getOidFieldName(fc):
    #returns the Objectid field of a fc.
    fc_desc = arcpy.Describe(fc)
    oidFieldName = fc_desc.oidFieldName
    del fc_desc
    return oidFieldName

def arrayToTree(array, firstNode):
    for item in array:
        nodeName = item[0]
        nodeCode = item[1]
        altCode = item[2]
        childrenArray = item[3]
        newNode = Node(nodeName, nodeCode, altCode)
        firstNode.add_child(newNode)
        hasChildren = len(childrenArray) > 0
        if hasChildren:
            arrayToTree(childrenArray, newNode)

def arrayToTree_old(array, firstNode):
    for item in array:
        nodeName = item[0]
        nodeCode = item[1]
        childrenArray = item[2]
        newNode = Node(nodeName, nodeCode)
        firstNode.add_child(newNode)
        hasChildren = len(childrenArray) > 0
        if hasChildren:
            arrayToTree(childrenArray, newNode)

def findNodesAbove(node,val,array):
    #Appends to array every node that its value is above val.
    if node.value>val:
        array.append(node)
    for child in node.children:
        findNodesAbove(child,val,array)

def findNode_rec(node, codedValue, array):
    #Appends to array every node that its coded value == the one
    #provided as variable.
    if node.codedValue == codedValue:
        array.append(node)
    for child in node.children:
        findNode_rec(child, codedValue, array)

def findNode(rootNode, codedValue):
    #Returns the first node encountered that has the same codedValue.
    arr = []
    findNode_rec(rootNode, codedValue, arr)
    if arr:
        return arr[0]
    else:
        #none found - return an empty node.
        return Node()

def findNodeByName_rec(node, name, array):
    #Appends to array every node that its name  == the one
    #provided as variable.
    if node.name == name:
        array.append(node)
    for child in node.children:
        findNodeByName_rec(child, name, array)

def findNodeByName(rootNode, name):
    #Returns the first node encountered that has the same name.
    arr = []
    findNodeByName_rec(rootNode, name, arr)
    if arr:
        return arr[0]
    else:
        #none found - return an empty node.
        return Node()

def findNodesWithAlternative_rec(node, array):
    #Appends to array every node that has an alternative code.
    if node.hasAlternative():
        array.append(node)
    for child in node.children:
        findNodesWithAlternative_rec(child, array)

def findNodesWithAlternative(rootNode):
    #Returns a list of nodes with alternative codes.
    arr = []
    findNodesWithAlternative_rec(rootNode, arr)
    return arr

def verifyAlternativeNodes(rootNode, speciesDictionary):
    """
    Every node under root, that has an alternative code,
    must have a corresponding node under root.
    For example, if node with code 1101
    has alternative code 1100 → make sure 1100 exists.
    -rootNode: top-most node object.
    -speciesDictionary: pre-calculated dict of:
        {codedValue <int>: species name <str>}
        every KEY represents a self-node that exists
        in JSON and root.
    Collects all the nodes without corresponding alternatives,
    and post them in the program as Error.
    """
    nodesWithAlternative = findNodesWithAlternative(rootNode)
    nodesWithoutTarget = []
    for node in nodesWithAlternative:
        if not int(node.altCode) in speciesDictionary.keys():
            nodesWithoutTarget.append(node)
    
    if nodesWithoutTarget:
        #for every node add a warning,
        #at the end ad an error in order to crash.
        warning = 'JSON file problems: could not find alternative codes:'
        arcpy.AddWarning(warning)
        for node in nodesWithoutTarget:
            warning = "-species %s %s: didn not find code %s" \
            % (node.codedValue, node.name, node.altCode)
            arcpy.AddWarning(warning)
        arcpy.AddError("Please fix JSON file, see details in the warnings above.")

def translate(input_string, translationDict):
    """
    Takes a string, if it is a key of translationDict:
    return the key's value. Else: return input_string.
    If the string is splittable - translate each split value
    and return a joined string.
    """
    if hasattr(input_string, 'split'):
        processedValues = []
        input_string_splitted = input_string.split(',')
        for splitValue in input_string_splitted:
            if splitValue in translationDict.keys():
                processedValues.append(translationDict[splitValue])
            else:
                processedValues.append(splitValue)
        joinedValues = ','.join(processedValues)
        return joinedValues
    else:
        return input_string

def replaceInList(input_list, value_from, value_to):
    """
    Check each list item if it is exactly equal to value_from,
    replace it with value_to, and return the modified list.
    """
    output_list = []
    for v in input_list:
        if v == value_from:
            output_list.append(value_to)
        else:
            output_list.append(v)
    return output_list

#CLASSES
class FeatureClass:
    def __init__(self, fullPath):
        if arcpy.Exists(fullPath):
            self.desc = arcpy.Describe(fullPath)
            if hasattr(self.desc,'shapeType'):
                #shapeType → 'Point', 'Polygon'
                self.shapeType = self.desc.shapeType
            self.name = self.desc.name
            self.fullPath = self.desc.catalogPath
            self.workspace = self.desc.path
            self.oidFieldName = self.desc.oidFieldName
            self.wsDomains = arcpy.Describe(self.workspace).domains
            self.relationships = {
                #'nickname': RelationshipClass,
            }
            #fieldCodesPrefix - generally not in use, unless declared.
            self.fieldCodesPrefix = None
        else:
            arcpy.AddWarning("Feature class or table does not exist:\n" + fullPath)
    
    def __repr__(self):
        return "FC: " + self.name

    def fieldsToTable(self, baseNumber):
        # For self-use only. 
        # Creates a table
        tableName = self.name + "_fields"
        createTable_result = arcpy.management.CreateTable(self.workspace, tableName)
        newTable = FeatureClass(arcpy.Describe(createTable_result).catalogPath)
        arcpy.management.AddField(newTable.fullPath, 'code', "LONG")
        for fieldName in ['tableName', 'name', 'alias', 'type', 'domain']:
            arcpy.management.AddField(newTable.fullPath, fieldName, "TEXT")
        fieldCode = baseNumber
        fieldIc = arcpy.InsertCursor(newTable.fullPath)
        for field in self.desc.fields:
            fieldRow = fieldIc.newRow()
            fieldRow.setValue('code',fieldCode)
            fieldCode += 1
            fieldRow.setValue('tableName',self.name)
            fieldRow.setValue('name',field.name)
            fieldRow.setValue('alias',field.aliasName)
            fieldRow.setValue('type',field.type)
            fieldRow.setValue('domain',field.domain)
            fieldIc.insertRow(fieldRow)
        del fieldIc
        return "Fields table created:\n" + tableName

class Organizer:
    #An object that holds data models.
    def __init__(self, stands, sekerpoints, sekerpointsRelationships):
        self.stands = FeatureClass(stands)
        self.sekerpoints = FeatureClass(sekerpoints)
        #Coordinate system of both FCs must be the same.
        self.checkSR([self.stands, self.sekerpoints])
        if self.stands.workspace != self.sekerpoints.workspace:
            arcpy.AddError('Stands and seker points are not in the same workspace.')
        arcpy.env.workspace = self.stands.workspace
        self.relationships = {
            #'nickname': RelationshipClass,
        }
        #Create and bind RelationshipClasses existing relationships between
        #and its related tables.
        for nickname, relTup in sekerpointsRelationships.items():
            #relTup = ('name of relationship class', field codes prefix <int>)
            relName = relTup[0]
            fieldCodesPrefix = relTup[1]
            #relationships <dict>: 'nickname': 'name of relationship class'.
            self.relationships[nickname] = RelationshipClass(relName, nickname, self.sekerpoints)
            #a patch to relationship's destination FC:
            #was made for verification of field existance.
            self.relationships[nickname].destination.fieldCodesPrefix = fieldCodesPrefix

    def checkSR(self, FC_list):
        wkid_list = [fc.desc.spatialReference.factoryCode for fc in FC_list]
        wkid_woDup = removeDup(wkid_list)
        if len(wkid_woDup) > 1:
            #Coordinate systems are not the same.
            concat = []
            for i in range(len(FC_list)):
                fcName = FC_list[i].name
                wkid = wkid_list[i]
                concat.append('-%s: %s.' % (fcName, wkid))
            concat = "\n".join(concat)
            arcpy.AddError('Feature classes must be of the same coordinate sysem.\n' + concat)

    def __repr__(self):
        return 'Organizer object'

class RelationshipClass:
    def __init__(self, relationshipName, nickname, originFC):
        self.desc = arcpy.Describe(relationshipName)
        self.name = self.desc.name
        self.nickname = nickname
        self.fullPath = self.desc.catalogPath
        self.workspace = self.desc.path
        #Check that originFC == relationship class' origin FC:
        if originFC.fullPath !=  os.path.join(self.desc.workspace.catalogPath, self.desc.originClassNames[0]):
            arcpy.AddError("Origin FCs don't match between sekerpoints and relationship provided.")
        self.origin = originFC
        #Create a pointer to the destination FC here:
        # Special case: relationship destination FC already exists → 
        # then use it and do not create a new FC instance.
        # Solution: check if destination name == sekerpoints name:
        if 'org' in globals():
            if org.sekerpoints.name == self.desc.destinationClassNames[0]:
                self.destination = org.sekerpoints
            else:
                self.destination = FeatureClass(self.desc.destinationClassNames[0])
        else:
            self.destination = FeatureClass(self.desc.destinationClassNames[0])
        #BIND BOTH WAYS to FC objects: origin and destination
        self.origin.relationships[self.nickname] = self
        self.destination.relationships[self.nickname] = self
        self.originKey_fieldName = self.desc.originClassKeys[0][0]
        self.foreignKey_fieldName = self.desc.originClassKeys[1][0]
    
    def __repr__(self):
        return 'Relationship class "%s": %s → %s' % (self.nickname, self.origin.name, self.destination.name)

    def getValues(self, fieldCodes, origKeyValue):
        """
        Gets values from rows in the destination FC.
        """
        fieldNames = [fieldsDict[code].name for code in fieldCodes]

        #Build SQL query and initiate search cursor:
        # SQL query for the destination FC as below:
        # "foreignKey_fieldName = originKeyValue"
        sqlQuery = buildSqlQuery_relationship(self, origKeyValue)
        values = []
        rel_Sc = arcpy.da.SearchCursor(
            self.destination.fullPath,
            fieldNames,
            where_clause = sqlQuery,
            )
        for rel_Row in rel_Sc:
            values.append(rel_Row)
        del rel_Sc
        return values

class Notifier:
    """
    A class for handling feature class row messages, warnings and errors.
    Contains a list of step name, type, message.
    As a new notification is added, an arcpy message/warning/error is 
    posted.
    """
    def __init__(self, fcRowObject, notificationsFieldCode):
        self.fcRow = fcRowObject
        self.fieldCode = notificationsFieldCode
        #Message prefix: a stamp to be added before each message:
        #Feature class name: stands_BarGiora, OBJECTID_1 = 106.
        self.messagePrefix = "Feature class: %s, %s = %s. " % (self.fcRow.FC.name, self.fcRow.FC.oidFieldName, self.fcRow.id)
        self.prefixSign = "~>"
        self.notifications = []

    def __repr__(self):
        notificationsCount = len(self.notifications)
        return "Notifier object, notifications count: %s." % notificationsCount

    def add(self, stepName, notificationType, message):
        #Creates a Notification object
        notification = Notification(stepName, notificationType, message)
        self.notifications.append(notification)
        txt = self.messagePrefix + "\n\t%s[%s]: %s" % (self.prefixSign, notification.stepName, notification.message)
        #Post based on the type of the notification:
        if notification.notificationType == 'message':
            arcpy.AddMessage(txt)
        elif notification.notificationType == 'warning':
            arcpy.AddWarning(txt)
        elif notification.notificationType == 'error':
            arcpy.AddError(txt)
    
    def concat(self):
        """
        Returns a string for notifications field.
        Example:
        ~>[step name]: message.
        ~>...
        """
        textRows = []
        for notification in self.notifications:
            stepName = notification.stepName
            message = notification.message
            txt = "%s[%s]: %s" % (self.prefixSign, stepName, message)
            textRows.append(txt)
        return "\n".join(textRows)

    def write(self):
        """
        Write the output of self.concat() method into notes field
        of code self.fieldCode.
        """
        txt = self.concat()
        self.fcRow.writeSelf(self.fieldCode, txt)

class Notification:
    def __init__(self, stepName, notificationType, message):
        self.stepName = stepName
        #Notification type can be: 'message' / 'warning' / 'error'
        self.notificationType = notificationType
        self.message = message

class FcRow:
    #Basic object for StandPolygon and SekerPoint.
    #Created for each row in stand or seker FCs.
    #Conatains common __init___ and data aquisition methods.
    def __init__(self, row, FC):
        self.row = row
        self.FC = FC
        self.id = self.row.getValue(self.FC.oidFieldName)

    def getSelfValue(self, fieldCodes):
        """
        Gets value\s from the row itself.
        - fieldCodes - list of codes or a single (see .getRelatedValues comments...).
        Returns a list of values or a single value, accordings to fieldCodes parameter.
        """
        fieldCodes_isList = type(fieldCodes) == list
        if fieldCodes_isList:
            fieldNames = [fieldsDict[code].name for code in fieldCodes]
        else:
            fieldNames = [fieldsDict[fieldCodes].name]
        
        values = [self.row.getValue(fieldName) for fieldName in fieldNames]

        #Return value/s:
        if fieldCodes_isList:
            return values
        else:
            return values[0]

    def getRelatedValues(self, relationshipNickname, fieldCodes):
        """
        Gets values from rows in the destination FC.
        - relationshipNickname - relationship nickname, must be related to FC.
        - fieldCodes - COULD BE ONE OF THE TWO BELOW:
            A) LIST of field codes from which the values will be obtained.
            B) A non list, the code itselt.
            Depending on the input, the method will return a list or a single value,
            respectively.
        Returns a list of values or a single value, accordings to fieldCodes parameter.
        """
        relationshipClass = self.FC.relationships[relationshipNickname]
        fieldCodes_isList = type(fieldCodes) == list
        if fieldCodes_isList:
            fieldNames = [fieldsDict[code].name for code in fieldCodes]
        else:
            fieldNames = [fieldsDict[fieldCodes].name]
        originKeyFieldName = relationshipClass.originKey_fieldName
        origKeyValue = self.row.getValue(originKeyFieldName)

        #Build SQL query and initiate search cursor:
        # SQL query for the destination FC as below:
        # "foreignKey_fieldName = originKeyValue"
        sqlQuery = buildSqlQuery_relationship(relationshipClass, origKeyValue)
        values = []
        rel_Sc = arcpy.da.SearchCursor(
            relationshipClass.destination.fullPath,
            fieldNames,
            where_clause = sqlQuery,
            )
        for rel_Row in rel_Sc:
            values.append(rel_Row)
        del rel_Sc

        #Return value/s:
        if fieldCodes_isList:
            return values
        else:
            return [value[0] for value in values]

    def writeSelf(self, fieldCodes, values):
        """
        Write value\s to the row itself.
        - fieldCodes - list of codes or a single (see .getRelatedValues comments...).
        - values - same as above but for value\s.
        """
        fieldCodes_isList = type(fieldCodes) == list
        values_isList = type(values) == list

        #fieldCodes and values must be of the both lists or both non-lists:
        sameType = fieldCodes_isList - values_isList == 0
        if not sameType:
            raise Exception('fieldCodes(%s) and values(%s) are of different types' % (type(fieldCodes), type(values)))

        #from now on, assume that input values are of the same type.
        inputsAreLists = fieldCodes_isList
        if inputsAreLists:
            #must have the same length:
            sameLength = len(fieldCodes) == len(values)
            if sameLength:
                #translate field codes to names,
                #values are a list of values anyway.
                fieldNames = [fieldsDict[code].name for code in fieldCodes]
            else:
                raise Exception('length of fieldCodes != values.')
        else:
            fieldNames = [fieldsDict[fieldCodes].name]
            values = [values]
        
        #Create a list of tuples [(field name <str>, value), ...]
        tupList = [(fieldNames[i],values[i]) for i in range(len(fieldNames))]

        for fieldName, value in tupList:
            #For string fields - check that the length of the field > length of value.
            destinationField = [fieldObj for fieldObj in arcpy.Describe(self.FC.fullPath).fields if fieldObj.name.lower() == fieldName.lower()][0]
            if destinationField.type == 'String' and type(value) is str:
                if destinationField.length < len(value):
                    #Add error notification OUTSIDE notifier object
                    #since not every object based on FcRow has a Notifier,
                    #and the tool will crash with an error anyway.
                    txt = 'writeSelf error: field "%s" (length: %s) is not long enough for its value:\n"%s" (length: %s).' % \
                    (destinationField.name, destinationField.length, value, len(value))
                    arcpy.AddError(txt)
            self.row.setValue(fieldName, value)
            #row won't be written until the method .updateRow() will
            #be called on the update cursor object, after the construction
            #of FcRow object finished.
        return

    def writeRelated(self, relationshipNickname, fieldCodes = [], values = []):
        """
        Write value\s to related tables by creating A SINGLE new row.
        In order to properly relate the origin and destination FCs:
        the origin field will be queried from self, and its value 
        will be inserted to the destination field of the new row
        created.
        If the FcRow object (self) has a .stamp attribute, its fields
        and values will be added to the new row that is being created.
        parameters:
        - fieldCodes - list of codes or a single (see .getRelatedValues comments...).
        - values - same as above but for value\s.
        """
        
        #Creating the tuple list for the INPUT fields and values.
        fieldCodes_isList = type(fieldCodes) == list
        values_isList = type(values) == list

        #fieldCodes and values must be of the both lists or both non-lists:
        sameType = fieldCodes_isList - values_isList == 0
        if not sameType:
            raise Exception('fieldCodes(%s) and values(%s) are of different types' % (type(fieldCodes), type(values)))

        #from now on, assume that input values are of the same type.
        inputsAreLists = fieldCodes_isList
        if inputsAreLists:
            #must have the same length:
            sameLength = len(fieldCodes) == len(values)
            if sameLength:
                #translate field codes to names,
                #values are a list of values anyway.
                fieldNames = [fieldsDict[code].name for code in fieldCodes]
            else:
                raise Exception('length of fieldCodes != values.')
        else:
            fieldNames = [fieldsDict[fieldCodes].name]
            values = [values]
        
        #Create a list of tuples [(field name <str>, value), ...]
        tupList = [(fieldNames[i],values[i]) for i in range(len(fieldNames))]
        #End of creating the tuple list for the INPUT fields and values.

        #Crate a relationship tuple (foreign field name, origKeyValue)
        # based on rel class.
        # (similar to .getRelatedValues() method).
        relationshipClass = self.FC.relationships[relationshipNickname]
        foreignKeyFieldName = relationshipClass.foreignKey_fieldName
        originKeyFieldName = relationshipClass.originKey_fieldName
        origKeyValue = self.row.getValue(originKeyFieldName)
        relationshipTuple = (foreignKeyFieldName, origKeyValue)
        tupList.append(relationshipTuple)
        
        #If FcRow object (self) has attribute of stamp - 
        #add its values to tupList.
        if hasattr(self, 'stamp'):
            #stamp is a list of tuples built like tupList.
            #add only fields that appear in destination featureclass:
            destinationFieldNames = [f.name.lower() for f in relationshipClass.destination.desc.fields]
            for tup in self.stamp:
                fName = tup[0]
                if fName.lower() in destinationFieldNames:
                    tupList.append(tup)

        #validate string fields lengths:
        destinationFields = {f.name.lower(): f for f in relationshipClass.destination.desc.fields}
        for fName, value in tupList:
            destinationField = destinationFields[fName.lower()]
            if destinationField.type == 'String' and type(value) is str:
                if destinationField.length < len(value):
                    #Add error notification OUTSIDE notifier object
                    #since not every object based on FcRow has a Notifier,
                    #and the tool will crash with an error anyway.
                    txt = 'writeSelf error: field "%s" (length: %s) is not long enough for its value:\n"%s" (length: %s).' % \
                    (destinationField.name, destinationField.length, value, len(value))
                    arcpy.AddError(txt)

        #write values
        fcPath = relationshipClass.destination.fullPath
        fNames = [tup[0] for tup in tupList]
        #(check if any field name appears more than once)
        hasDoubles = len(fNames) != len(set(fNames))
        if hasDoubles:
            txt = 'Fields list has duplications\n%s' % fNames
            raise Exception(txt)
        fValues = [tup[1] for tup in tupList]
        ic = arcpy.da.InsertCursor(fcPath, fNames)
        ic.insertRow(fValues)
        del ic
        return
    
    def updateRelated(self, relationshipNickname, fieldCodes = [], values = []):
        """
        Updates all rows of a related teble, without creating new rows.
        If the FcRow object (self) has a .stamp attribute, its fields
        and values will be added to the new row that is being created.
        parameters:
        - fieldCodes - list of codes or a single (see .getRelatedValues comments...).
        - values - same as above but for value\s.
        """
        
        #Creating the tuple list for the INPUT fields and values.
        fieldCodes_isList = type(fieldCodes) == list
        values_isList = type(values) == list

        #fieldCodes and values must be of the both lists or both non-lists:
        sameType = fieldCodes_isList - values_isList == 0
        if not sameType:
            raise Exception('fieldCodes(%s) and values(%s) are of different types' % (type(fieldCodes), type(values)))

        #from now on, assume that input values are of the same type.
        inputsAreLists = fieldCodes_isList
        if inputsAreLists:
            #must have the same length:
            sameLength = len(fieldCodes) == len(values)
            if sameLength:
                #translate field codes to names,
                #values are a list of values anyway.
                fieldNames = [fieldsDict[code].name for code in fieldCodes]
            else:
                raise Exception('length of fieldCodes != values.')
        else:
            fieldNames = [fieldsDict[fieldCodes].name]
            values = [values]
        
        #Create a list of tuples [(field name <str>, value), ...]
        tupList = [(fieldNames[i],values[i]) for i in range(len(fieldNames))]
        #End of creating the tuple list for the INPUT fields and values.

        #Build SQL query update cursor:
        # SQL query for the destination FC as below:
        # "foreignKey_fieldName = originKeyValue"
        # (similar to .getRelatedValues() method).
        relationshipClass = self.FC.relationships[relationshipNickname]
        originKeyFieldName = relationshipClass.originKey_fieldName
        origKeyValue = self.row.getValue(originKeyFieldName)
        sqlQuery = buildSqlQuery_relationship(relationshipClass, origKeyValue)
        
        #If FcRow object (self) has attribute of stamp - 
        #add its values to tupList.
        if hasattr(self, 'stamp'):
            #stamp is a list of tuples built like tupList.
            #add only fields that appear in destination featureclass:
            destinationFieldNames = [f.name.lower() for f in relationshipClass.destination.desc.fields]
            for tup in self.stamp:
                fName = tup[0]
                if fName.lower() in destinationFieldNames:
                    tupList.append(tup)
        
        #If tupList is empty it means nothing to update - end function
        if len(tupList) == 0:
            return

        #validate string fields lengths:
        destinationFields = {f.name.lower(): f for f in relationshipClass.destination.desc.fields}
        for fName, value in tupList:
            destinationField = destinationFields[fName.lower()]
            if destinationField.type == 'String' and type(value) is str:
                if destinationField.length < len(value):
                    #Add error notification OUTSIDE notifier object
                    #since not every object based on FcRow has a Notifier,
                    #and the tool will crash with an error anyway.
                    txt = 'writeSelf error: field "%s" (length: %s) is not long enough for its value:\n"%s" (length: %s).' % \
                    (destinationField.name, destinationField.length, value, len(value))
                    arcpy.AddError(txt)

        #write values
        fcPath = relationshipClass.destination.fullPath
        fNames = [tup[0] for tup in tupList]
        #(check if any field name appears more than once)
        hasDoubles = len(fNames) != len(set(fNames))
        if hasDoubles:
            txt = 'Fields list has duplications\n%s' % fNames
            raise Exception(txt)
        fValues = [tup[1] for tup in tupList]
        rel_Uc = arcpy.UpdateCursor(fcPath, where_clause = sqlQuery)
        for rel_Row in rel_Uc:
            for i in range(len(fValues)):
                rel_Row.setValue(fNames[i], fValues[i])
            rel_Uc.updateRow(rel_Row)
        del rel_Uc
        return

    def deleteRelated(self, relationshipNickname, additionalQuery = ""):
        """
        Deletes rows in the destination FC.
        Parameters:
        - relationshipNickname - relationship nickname, must be related to FC.
        - additionalQuery - a query expression.
        The destination rows will always be among the rows related to
        the current origin row. And can be more specified with an
        additional query inside it, using AND operator.
        For example:
               ↓related rows              ↓additional condition
        sql = "parentglobalid = {...} AND globalid = {...}"
    
        If additionalQuery is not defined - the method deletes all
        related rows.
        """
        relationshipClass = self.FC.relationships[relationshipNickname]
        originKeyFieldName = relationshipClass.originKey_fieldName
        origKeyValue = self.row.getValue(originKeyFieldName)

        #Build SQL query and initiate update cursor:
        # SQL with 1/2 components:
        # 1) sqlQuery_base - select related rows. 
        #    ("foreignKey_fieldName = originKeyValue")
        # and, if provided
        # 2) additionalQuery - select from related rows.
        # SQL query for the destination FC as below:
        # 
        sqlQuery_base = buildSqlQuery_relationship(relationshipClass, origKeyValue)
        if additionalQuery:
            sqlQuery = " AND ".join([sqlQuery_base, additionalQuery])
        else:
            sqlQuery = sqlQuery_base
        
        rel_Uc = arcpy.da.UpdateCursor(
            relationshipClass.destination.fullPath,
            ['OID@'],
            where_clause = sqlQuery,
            )
        for rel_Row in rel_Uc:
            print(rel_Row[0]) #INDICATE
            rel_Uc.deleteRow()
        del rel_Uc

class StandPolygon(FcRow):
    #Each poygon in stands FC gets an object.
    def __init__(self, row, standsFC):
        FcRow.__init__(self, row, standsFC)
        arcpy.AddMessage('Started calculating: stand %s = %s'% (self.FC.oidFieldName, self.id))
        self.notifier = Notifier(self, 50079)
        self.stamp = self.getStamp()
        #Validate and handle stand number duplications:
        self.validateStandDuplication()
        self.points = self.getPoints(self.FC.relationships['sp'])
        self.N_points = len(self.points)

        self.calculateAndWrite()
        self.notifier.write()

    def getPoints(self, relationship):
        destinationFC = relationship.destination
        originValue = self.row.getValue(relationship.originKey_fieldName)
        #Build SQL query and initiate search cursor:
        sqlQuery = buildSqlQuery_relationship(relationship, originValue)
        points = []
        rel_Uc = arcpy.UpdateCursor(
            destinationFC.fullPath,
            sort_fields = '%s A' % destinationFC.oidFieldName,
            where_clause = sqlQuery,
            )
        for rel_Row in rel_Uc:
            point = SekerPoint(self, rel_Row, destinationFC)
            rel_Uc.updateRow(point.row)
            points.append(point)
        del rel_Uc
        return points

    def getStamp(self):
        """
        Returns a list of tuples of [(fieldName, value), ...]
        that are unique to the specific StandPolygon.
        Enables to write a new related row.
        DOES NOT contain relationship origin / destination field and values.
        """
        #field codes to be queried as input.
        query_fieldCodes = [
            50002, #forest number
            50003, #helka number
            50004  #stand number
        ]

        rawValues = self.getSelfValue(query_fieldCodes)

        for_no = rawValues[0]
        helka = rawValues[1]
        stand_no = rawValues[2]

        #create a standAddress value by concat:
        #<FOR_NO>_<HELKA> / <STAND_NO>
        standAdress = "%s_%s / %s" % (for_no, helka, stand_no)
        
        #stampTuples: list of tuples to be returned
        #Notice! the field names here are of the related tables.
        #The dict rel_fNames makes sure the field names correspond to the fields excel table.
        rel_fNames = {
            'FOR_NO': fieldsDict[stands_relatedTables_globalFieldCodes[2]].name,
            'HELKA': fieldsDict[stands_relatedTables_globalFieldCodes[3]].name,
            'STAND_NO': fieldsDict[stands_relatedTables_globalFieldCodes[4]].name,
            'standAddress': fieldsDict[stands_relatedTables_globalFieldCodes[1]].name,
        }
        stampTuples = [
            (rel_fNames['FOR_NO'], for_no),
            (rel_fNames['HELKA'], helka),
            (rel_fNames['STAND_NO'], stand_no),
            (rel_fNames['standAddress'], standAdress)
        ]
        return stampTuples

    def validateStandDuplication(self):
        """
        Checks if this stand number appears more than once in its helka.
        If it does - 
        1) update self.stamp
        2) update helka's stands list
        3) update stand number in stand's related points and tables
        """
        helka = self.stamp[1][1]
        stand_id = self.id
        stand_no_old = self.stamp[2][1]
        calculated = False #default value
        #Check the helka's stands list in it's FC object
        if hasattr(self.FC,'standsByHelka'):
            if helka in self.FC.standsByHelka.keys():
                calculated = True
                standsList = self.FC.standsByHelka[helka]
        else:
            #first stand in the feature class.
            #A list of stand numbers for every helka:
            #{helka <int>: [(stand <int>, objectid <oid>), ...], ...}
            self.FC.standsByHelka = {}

        if not calculated:
            #it is either:
            # 1) the first stand in the feature class.
            # 2) the first stand in it's helka.

            #build the list of all the stands in the helka:
            helkaField = forestAddressFieldNames[1]
            standField = forestAddressFieldNames[2]
            objectidField = self.FC.oidFieldName

            field_delimited = arcpy.AddFieldDelimiters(self.FC.workspace, helkaField)
            sql_exp = """{0} = {1}""".format(field_delimited, helka)
            standsList = []
            helka_sc = arcpy.da.SearchCursor(
                self.FC.fullPath,
                [standField, objectidField],
                sql_exp
                )
            for tup in helka_sc:
                standsList.append(tup)
            del helka_sc
            #sort by stand number:
            standsList.sort(key=lambda x: x[0])
            self.FC.standsByHelka[helka] = standsList
        
        #check for duplications of this spcific stand
        hasDuplicaions = len([t for t in standsList if t[0] == stand_no_old]) > 1
        if hasDuplicaions:
            #get a new stand number:
            stand_no_new = max([t[0] for t in standsList]) + 1
            #1) update standsList:
            tup_old = (stand_no_old, stand_id)
            tup_new = (stand_no_new, stand_id)
            self.FC.standsByHelka[helka].remove(tup_old)
            self.FC.standsByHelka[helka].append(tup_new)
            #2) update stand value
            self.writeSelf(50004, stand_no_new)
            #3) update self.stamp
            self.stamp = self.getStamp()
            #4) update related tables
            for relationship in self.FC.relationships.values():
                self.updateRelated(relationship.nickname)



        else:
            pass


        return

    def coniferForest(self, presence, presenceType):
        #Returns True if sub forest conifer forest meets criteria.
        #Convert presenceConifer to index based on domain,
        #obtain threshold based on presenceConiferType.
        #Method variables are results of methods:
        #c__presenceconifer() & c__presencetype() respectively.
        
        #presence_domain = every possible value of presence
        presence_domain = [
            None,
            "אין",
            "1-20",
            "21-50",
            "51-100",
            "מעל 100",
        ]
        presence_thresholdByType = {
            "נטיעה": 3,
            "התחדשות_טבעית": 4,
            "נטיעה,התחדשות_טבעית": 3
        }

        if presenceType in presence_thresholdByType.keys():
            threshold = presence_thresholdByType[presenceType]
            index = presence_domain.index(presence)
            return index >= threshold
        else:
            return False
    
    def broadleafForest(self, presence, presenceType):
        #Returns True if sub forest broadleaf forest meets criteria.
        #Convert presenceBroadLeaf to index based on domain,
        #obtain threshold based on presenceBroadLeafType.
        #Method variables are results of methods:
        #c__presencebroadleaf() & c__presencetype() respectively.
        
        #presence_domain = every possible value of presence
        presence_domain = [
            None,
            "אין",
            "1-5",
            "6-10",
            "11-20",
            "מעל 20",
        ]
        presence_thresholdByType = {
            "נטיעה": 3,
            "התחדשות_טבעית": 5,
            "נטיעה,התחדשות_טבעית": 3
        }

        if presenceType in presence_thresholdByType.keys():
            threshold = presence_thresholdByType[presenceType]
            index = presence_domain.index(presence)
            return index >= threshold
        else:
            return False

    def calculateAndWrite(self):
        """
        A module that runs calculation methods (c__...) and
        writes their results into stand row, or its related
        tables.
        """
        """
        The following attributes with the prefix "v__" for VALUE of calculations.
        The rest of the name, after the prefix, after the field name.
        """
        #a variable for order:
        self.forestlayerVegform_calculated = False
        
        self.v__start_year = self.c__start_year()
        self.writeSelf(50027, self.v__start_year)
        self.v__age_group = self.c__age_group(self.v__start_year)
        self.writeSelf(50028, self.v__age_group)
        ###

        self.v__planttype = self.c__planttype()
        for planttype, percent in self.v__planttype.items():
            self.writeRelated('st2', [52001, 52002], [planttype, percent])
        self.v__planttype_desc = self.c__planttype_desc(self.v__planttype)
        self.writeSelf(50058, self.v__planttype_desc)

        self.v__presenceconifer = self.c__presenceconifer()
        self.writeSelf(50063, self.v__presenceconifer)
        self.v__presenceconifertype = self.c__presencetype(40056)
        self.writeSelf(50064, self.v__presenceconifertype)
        self.isConiferForest = self.coniferForest(
            self.v__presenceconifer, 
            self.v__presenceconifertype
        )

        self.v__presencebroadleaf = self.c__presencebroadleaf()
        self.writeSelf(50065, self.v__presencebroadleaf)
        self.v__presencebroadleaftype = self.c__presencetype(40058)
        self.writeSelf(50066, self.v__presencebroadleaftype)
        self.isBroadleafForest = self.broadleafForest(
            self.v__presencebroadleaf,
            self.v__presencebroadleaftype
        )

        self.v__logiclayers = self.c__logiclayers()
        oedered_fieldCodes = {
            #order: [forest layer, veg form, layer cover, layer desc]
            'primary': [50029,50030,50031,50032],
            'secondary': [50033,50034,50035,50036]
        }
        for order, layerResult in self.v__logiclayers.items():
            #oeder is the key of the result dict, can be primary/secondary
            #to fit the keys fieldCodes.
            fieldCodes = oedered_fieldCodes[order]
            values = layerResult.getValuesToWrite()
            self.writeSelf(fieldCodes, values)

        #groundlevelfloorvegform
        self.v__groundlevelfloorvegform = self.c__groundlevelfloorvegform()
        self.writeSelf(50089, self.v__groundlevelfloorvegform)

        self.v__standvegform = self.c__standvegform(self.v__logiclayers)
        self.writeSelf(50037, self.v__standvegform)

        self.v__generaldensity = self.c__generaldensity()
        self.writeSelf(50042, self.v__generaldensity)

        #A dictionary of layerNum and their sorted field codes:
        #  {layerNum <int>: [vegForm,layerCover,speciesNames,speciesCodes], ...}
        forestLayer_numsFields = {
            4:[50046,50047,50048,50049],
            3:[50050,50051,50052,50053],
            2:[50054,50055,50056,50057],
        }
        #A dictionary to store vegform before translation:
        #  {layerNum <int>: vegForm, ...}
        self.layerVegForm = {}
        for layerNum, fieldCodes in forestLayer_numsFields.items():
            vegForm = self.c__forestLayer__vegForm(layerNum)
            #store value before translation to be used later (covtype)
            self.layerVegForm[layerNum] = vegForm
            #translate vegform to write into the layer:
            vegForm_translated = translate(vegForm,subForestVegForm_translation)
            self.forestlayerVegform_calculated = True
            layerCover = self.c__forestLayer__layerCover(layerNum)
            species_raw = self.c__forestLayer__species(layerNum)
            speciesNames = species_raw['names']
            speciesCodes = species_raw['codes']
            self.writeSelf(fieldCodes, [vegForm_translated,layerCover,speciesNames,speciesCodes])

        ### COVTYPE COMPLEX MUST BE CALLED after C__FORESTlAYER__...() .
        self.v__covtypeRel = self.c__covtypeRel()
        for species, proportion in self.v__covtypeRel:
            self.writeRelated('st3', [53001, 53002], [species, proportion])
        self.v__covtype_desc = self.c__covtype_desc(self.v__covtypeRel)
        self.writeSelf(50040, self.v__covtype_desc)

        self.v__covtype = self.c__covtype(
            self.v__covtypeRel,
            self.v__logiclayers
        )
        self.writeSelf(50038, self.v__covtype.code)
        self.writeSelf(50039, self.v__covtype.str)

        self.v__forestagecomposition = self.c__forestagecomposition()
        self.writeSelf(50041, self.v__forestagecomposition)

        self.v__standdensity = self.c__standdensity(self.v__generaldensity)
        self.writeSelf(50043, self.v__standdensity)

        self.v__coniferforestage = self.c__coniferforestage()
        self.writeSelf(50045, self.v__coniferforestage)

        self.v__relativedensity = self.c__relativedensity(
            self.v__coniferforestage,
            self.v__generaldensity,
            input_beitGidul
            )
        self.writeSelf(50044, self.v__relativedensity)


        self.v__supSpecies_trees = self.c__subSpecies(40074)
        self.writeSelf(
            [50059,50060],
            [self.v__supSpecies_trees['names'],self.v__supSpecies_trees['codes']]
            )
        self.v__supSpecies_shrubs = self.c__subSpecies(40082)
        self.writeSelf(
            [50061,50062],
            [self.v__supSpecies_shrubs['names'],self.v__supSpecies_shrubs['codes']]
            )

        self.v__deadtreespercent = self.c__treeharmindex(40059)
        self.writeSelf(50068, self.v__deadtreespercent)

        self.v__inclinedtreespercent = self.c__treeharmindex(40060)
        self.writeSelf(50069, self.v__inclinedtreespercent)

        self.v__brokentreespercent = self.c__treeharmindex(40061)
        self.writeSelf(50070, self.v__brokentreespercent)

        self.v__brurnttreespercent = self.c__treeharmindex(40062)
        self.writeSelf(50071, self.v__brurnttreespercent)

        self.v__treeharm = self.c__treeharm(
            [
                self.v__deadtreespercent,
                self.v__inclinedtreespercent,
                self.v__brokentreespercent,
                self.v__brurnttreespercent
            ]
        )
        self.writeSelf(50067, self.v__treeharm)

        self.v__vitalforest = self.c__vitalforest()
        for defect, impact in self.v__vitalforest.items():
            self.writeRelated(
                'st4',
                [54001,54002],
                [defect, impact]
            )
        self.v__vitalforest_desc = self.c__vitalforest_desc(self.v__vitalforest)
        self.writeSelf(50073, self.v__vitalforest_desc)
        self.v__forestdegeneration = self.c__forestdegeneration()
        self.writeSelf(50072, self.v__forestdegeneration)

        self.v__invasivespecies = self.c__invasivespecies()
        for invSp, epicenter in self.v__invasivespecies.items():
            self.writeRelated(
                'st1',
                [51001,51002],
                [invSp, epicenter]
            )
        self.v__invasivespecies_desc = self.c__invasivespecies_desc(self.v__invasivespecies)
        self.writeSelf(50074, self.v__invasivespecies_desc)

        self.v__naturalvalues = self.c__naturalvalues()
        self.writeSelf(50075, self.v__naturalvalues['main'])
        self.writeSelf(50103, self.v__naturalvalues['details'])

        self.v__roadsidesconditions = self.c__roadsidesconditions()
        self.writeSelf(50076, self.v__roadsidesconditions['main'])
        self.writeSelf(50104, self.v__roadsidesconditions['details'])

        self.v__limitedaccessibilitytype = self.c__limitedaccessibilitytype()
        self.writeSelf(50077, self.v__limitedaccessibilitytype['main'])
        self.writeSelf(50105, self.v__limitedaccessibilitytype['details'])

        self.v__foresthazards = self.c__foresthazards()
        self.writeSelf(50078, self.v__foresthazards['main'])
        self.writeSelf(50106, self.v__foresthazards['details'])


        self.v__totalcoverage = self.c__totalcoverage()
        self.writeSelf(50088, self.v__totalcoverage)

        self.v__date = self.c__date()
        self.writeSelf(50085, self.v__date)

        self.v__dunam = self.c__dunam()
        self.writeSelf(50086, self.v__dunam)

        pass

    #Calculation methods that belong to the tool fields logic:
    #   -prefix: "c__" for calculation.
    #   -name: after the field name to be calculated (lowercase).
    #          (שמות השדות והחישובים מתוך מסמך "איחוד נקודות לעומד אפיון תוצר 040922")

    def c__start_year(self):
        values = self.getRelatedValues('sp', 40014)
        validValues = []
        for rawValue in values:
            if isIntable(rawValue) and rawValue != '0':
                validValues.append(int(rawValue))
        if len(validValues) > 0:
            return math.floor(average(validValues))
        else:
            return None

    def c__age_group(self, start_year):
        """
        Takes start year and returns age group category <str>.
        start_year - the year of planting, calculated before.
        """
        if isIntable(start_year):
            start_year = int(start_year)
            now_year = datetime.datetime.now().year
            time_passed = now_year - start_year + 1
            defaultValue = None
            startYear_categories = [
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
                (120, 'ותיק (106-120)')
                ]
            category = toCategory(time_passed, startYear_categories, defaultValue)
            del defaultValue, startYear_categories
            return category
        else:
            return None

    def c__logiclayers(self):
        """
        Calculates stand's primary and secondary layers' attributes:
        forest layer, veg form, layer cover, layer desc.
        """
        stepName = 'logiclayers'
        #The method returns outDict
        outDict = {
            "primary": LayerResult(),
            "secondary": LayerResult()
        }

        if self.N_points == 0:
            #If there are no points to go through,
            #return an empty outDict.
            return outDict
        
        #Every layer number (4-1) gets sum of cover average values:
        #layerNums_sumOfCoverAverages = {layerNum <int>: sum of cover average values <int>,}
        layerNums_sumOfCoverAverages = {layerNum:0 for layerNum in [4,3,2,1]}
        for point in self.points:
            primaryLayers = [layer for layer in point.layers.values() if layer.isPrimary]
            secondaryLayers = [layer for layer in point.layers.values() if layer.isSecondary]
            if primaryLayers:
                #If primaryLayers are returned, the list contains only one object.
                primaryLayer = primaryLayers[0]
                if primaryLayer.isValid:
                    layerNums_sumOfCoverAverages[primaryLayer.layerNum] += primaryLayer.layerCover_avg
            if secondaryLayers:
                secondaryLayer = secondaryLayers[0]
                if secondaryLayer.isValid:
                    layerNums_sumOfCoverAverages[secondaryLayer.layerNum] += secondaryLayer.layerCover_avg
        #Average the values to the number of points:
        layerNums_avg = {layerNum: math.ceil(summ/self.N_points) for layerNum, summ in layerNums_sumOfCoverAverages.items()}
        #Convert to cover <str>:
        layerNums_covers = {layerNum: toCategory(avg,layerCover_table1_backwardsList) for layerNum, avg in layerNums_avg.items()}

        #These are layer nums (4-1) that were assigned during classification of
        #primary and secondary layers:
        #(in order not to re-assign them)
        layerNumsToInvestigate = []

        #Find STAND's primary and secondary layer based on cover, 
        #like in classification script: first 'פתוח', then 'פזור'.
        for threshold_layerCoverNum in [3,2]:
            for layerNum, cover in layerNums_covers.items():
                #Before inspecting, make sure there is room to insert
                #more layers to outDict:
                roomForAssignment = False in [layer.assigned for layer in outDict.values()]
                if (layerNum in [4,3,2]) and roomForAssignment:
                    #convert cover <str> to coverNum <int>:
                    layerCoverNum = layerCover_table1[cover][0]
                    if layerCoverNum >= threshold_layerCoverNum and\
                        layerNum not in layerNumsToInvestigate:
                        #insert it as primary or secondary layer:
                        if not outDict['primary'].assigned:
                            outDict['primary'].assign(layerNum, cover)
                            layerNumsToInvestigate.append(layerNum)
                        elif not outDict['secondary'].assigned:
                            outDict['secondary'].assign(layerNum, cover)
                            layerNumsToInvestigate.append(layerNum)
            
        
        layerShortTextToInvestigate = []
        for layerResult in outDict.values():
            if layerResult.assigned:
                layerShortTextToInvestigate.append(layerResult.layerShortText)
        #Sum every veg form in every layer of interest (that was previosly
        # declared as primary or secondary).
        #layerNums_species: each layerNum <int> has a dictionary of 
        #{layerNum: {veg form <str>: sum of cover averages <float>, ...}, ...}
        layerNums_vegFormsDict = {num:{} for num in layerNumsToInvestigate}
        for point in self.points:
            #In each point, use only the layers that belong to stand's pri/sec
            #("layers to investigate"), and only if they are valid.
            relevantLayers = [point.layers[short] for short in layerShortTextToInvestigate if point.layers[short].isValid]
            for layer in relevantLayers:
                layerNum = layer.layerNum
                #get the desired value= cover average / N_vegForms
                numerator = layer.layerCover_avg
                denominator = len(layer.vegForms)
                quotient = math.ceil(numerator/denominator)
                for vegForm in layer.vegForms:
                    if vegForm in layerNums_vegFormsDict[layerNum].keys():
                        layerNums_vegFormsDict[layerNum][vegForm] += quotient
                    else:
                        layerNums_vegFormsDict[layerNum][vegForm] = quotient
        
        #Final logic for veg form:
        #After every relevant layerNum got a vegForm sums dict
        #in layerNums_vegFormsDict, the next step is to come out
        #with the final value of vegForm.
        #Mainly based on number of different vegForms in the layer:
        #1) One single vegForm: return it.
        #2) Two vegForms: one of the following options:
        #2a option) one is >=80% → return it.
        #2b option) none is >=80% → vegForm matrix.
        #3 and above) try to group-up the subordinates of 'רחבי עלים'
        #   these are: בוסתנים ומטעים, גדות נחלים, חורש.
        #   after grouping-up, repeat steps 1-3.
        #3*) If grouping has been made, or is not possible, 
        #   and number of different veg forms is still >= 3:
        #   → vegForm matrix with the two highest vegForms.
        
        for layerNum, vegFormDict in layerNums_vegFormsDict.items():
            #Find if layerNum was assigned to primary or secondary:
            if outDict['primary'].layerNum == layerNum:
                layerOrder = 'primary'
            else:
                layerOrder = 'secondary'
            
            
            #safety counter to activate if the condition of (N_vegForms >= 3) 
            #is met more than twice:
            safetyCounter = 0
            while True:
                #A risky condition, pay attention to 'break' statements,
                #appearing everywhere except after grouping.
                #In other words: this while loop runs once, unless a grouping
                #process occured - then it runs twice (if more - it's a bug).

                #convert to a list of tuples [(vegForm, sum of cover averages),...] 
                #in order to maintain the list ordered.
                vegFormTuples = list(vegFormDict.items())
                #Logic condition based on number of different vegForms:
                N_vegForms = len(vegFormTuples)
                if N_vegForms == 1:
                    first = vegFormTuples[0]
                    outDict[layerOrder].setVegForm(first[0])
                    break
                elif N_vegForms == 2:
                    #find the ratio between the first / the second:
                    first = vegFormTuples[0]
                    second = vegFormTuples[1]
                    ratio = first[1]/(first[1]+second[1])
                    if ratio >= 0.8:
                        #the first is dominant:
                        outDict[layerOrder].setVegForm(first[0])
                    elif ratio < 0.2:
                        #the second is dominant:
                        outDict[layerOrder].setVegForm(second[0])
                    else:
                        #neither is dominant:
                        matrixResult = forestVegFormCoordinator.solve(
                            [first[0], second[0]]
                        )
                        outDict[layerOrder].setVegForm(matrixResult)
                    break
                elif N_vegForms >= 3:
                    #end of grouping, next: another round of while-loop.
                    #add one to the safety counter:
                    safetyCounter += 1
                    if safetyCounter>2:
                        #this sould not happen, add warning and break from while loop.
                        txt = 'While-loop error with more than 3 different vegForms [layer num: %s].'%layerNum
                        self.notifier.add(stepName, 'warning', txt)
                        break
                    #Prepare for group-up:
                    groupable_vegForms = [
                        'בוסתנים_ומטעים',
                        'יער_גדות_נחלים',
                        'חורש'
                    ]
                    masterGroup_vegForm = 'רחבי-עלים'
                    #a dict to replace vegFormDict later:
                    vegFormDict_new = {}
                    #grouping condition:
                    groupable = False
                    for vegForm in vegFormDict.keys():
                        if vegForm in groupable_vegForms:
                            groupable = True
                    
                    if groupable:
                        for vegForm, value in vegFormDict.items():
                            if vegForm == masterGroup_vegForm:
                                #add broadleaf's self value to vegFormDict_new,
                                #under 'broadleaf'.
                                if vegForm in vegFormDict_new.keys():
                                    vegFormDict_new[vegForm] += value
                                else:
                                    vegFormDict_new[vegForm] = value
                            elif vegForm in groupable_vegForms:
                                #add groupable's value to vegFormDict_new,
                                #under 'broadleaf' (master).
                                if masterGroup_vegForm in vegFormDict_new.keys():
                                    vegFormDict_new[masterGroup_vegForm] += value
                                else:
                                    vegFormDict_new[masterGroup_vegForm] = value
                            else:
                                #the discussed vegForm belongs to neigher,
                                #just add it to its own entry.
                                vegFormDict_new[vegForm] = value
                        #update vegFormDict with the groupped, new one:
                        vegFormDict = vegFormDict_new
                    else:
                        #Sort descending by value and matrix the first two.
                        vegFormTuples.sort(key=lambda x: x[1], reverse = True)
                        first = vegFormTuples[0]
                        second = vegFormTuples[1]
                        matrixResult = forestVegFormCoordinator.solve(
                            [first[0], second[0]]
                        )
                        outDict[layerOrder].setVegForm(matrixResult)
                        break
                else:
                    #N_vegForms < 1: should not happen at all.
                    # if the code gets here, that means N_vegForms < 1:
                    #an error:
                    txt = 'length of vegForm dictionary is < 1'
                    self.notifier.add(stepName, 'error', txt)
                    break
        
        #Sub-forest inspection:
        #PAY ATTENTION! this part has a variation in method c__groundlevelfloorvegform()!
        #Assign and set vegForm of sub-forest layer, in a way
        #that is different from the forest layers.
        #Make sure there is room to insert
        #more layers to outDict:
        roomForAssignment = False in [layer.assigned for layer in outDict.values()]
        if roomForAssignment:
            #Get the vecant layer order to assign to:
            for order in ['primary', 'secondary']:
                if not outDict[order].assigned:
                    layerOrder = order
                    break
            #Replicate self.v__planttype to a local variable that is
            #not referenced, because its values might get changed.
            #-- NOTICE: this code block has a replica in c__covtype! --
            planttype = {k:v for k,v in self.v__planttype.items()}
            #lowForest booleans, self-describing:
            lowForest_boolList = [self.isConiferForest, self.isBroadleafForest]
            treesPresence = True in lowForest_boolList
            if treesPresence:
                #Set vegform:
                if lowForest_boolList == [True, True]:
                    vegForm = 'יער מעורב נמוך'
                elif lowForest_boolList == [True, False]:
                    vegForm = 'יער מחטני נמוך'
                elif lowForest_boolList == [False, True]:
                    vegForm = 'יער רחבי עלים נמוך'
                #Cover based on 'עצים'. Not lower than 'פזור', hence 4+ .
                percent = max([planttype['עצים'], 4])
                cover = toCategory(percent, layerCover_table1_backwardsList)
                outDict[layerOrder].assign(1, cover)
                outDict[layerOrder].setVegForm(vegForm)
            elif planttype['צומח_גדות_נחלים'] >= 30:
                percent = planttype['צומח_גדות_נחלים']
                vegForm = 'צומח_גדות_נחלים'
                #translate:
                vegForm = translate(vegForm, subForestVegForm_translation)
                cover = toCategory(percent, layerCover_table1_backwardsList)
                outDict[layerOrder].assign(1, cover)
                outDict[layerOrder].setVegForm(vegForm)
            else:
                planttype['שיחים'] += planttype['עצים'] + planttype['צומח_גדות_נחלים']
                planttype['עצים'] = 0
                planttype['צומח_גדות_נחלים'] = 0
                #The vegforms relevant for this step:
                vegForms = ['שיחים', 'בני_שיח', 'עשבוני']
                #vegForms_covers is a list of tuples: [(vegForm <str>, cover percent <int>), ...]
                #A tuple would be added only if cover percent >= 10 .
                vegForms_covers = [(vegform, planttype[vegform]) for vegform in vegForms if planttype[vegform] >= 10]
                if vegForms_covers:
                    #pick the first tuple, for it's the highest hierarchy of vegForms:
                    tup = vegForms_covers[0]
                    vegForm = tup[0]
                    #translate:
                    vegForm = translate(vegForm, subForestVegForm_translation)
                    percent = tup[1]
                    cover = toCategory(percent, layerCover_table1_backwardsList)
                    outDict[layerOrder].assign(1, cover)
                    outDict[layerOrder].setVegForm(vegForm)
                else:
                    #No veg form of the three mentioned above has cover >= 10:
                    #go to 'ללא כיסוי'.
                    vegForm = 'ללא_כיסוי'
                    #translate:
                    vegForm = translate(vegForm, subForestVegForm_translation)
                    #Cover returns 'גבוה (מעל 66%)'
                    cover = toCategory(100, layerCover_table1_backwardsList)
                    #Assign:
                    outDict[layerOrder].assign(1, cover)
                    outDict[layerOrder].setVegForm(vegForm)
                    #Add warning:
                    txt = 'sub-forest layer "%s".' % vegForm
                    self.notifier.add(stepName, 'warning', txt)
        
        #create layer description string for primary and secondary layers
        #(as long as the layer is assigned).
        #For every assigned layer, call the finalize() method.
        for layerRepr in outDict.values():
            layerRepr.finalize()
                

        return outDict

    def c__groundlevelfloorvegform(self):
        """
        Calculates stand's ground level floor veg form based on:
            -isConiferForest <bool>
            -isBroadleafForest <bool>
            -v__planttype <dict>
            -v__logiclayers {'primary': <obj>, 'secondary': <obj>}
        All the attributes mentioned above have to be calculated before
        this method is called.
        The logic of this method is identical to that of c__logiclayers, 
        in the part of #Sub-forest inspection. c__logiclayers would not
        necessarily calculate this step, but if it did - c__groundlevelfloorvegform
        would take the value calculated for ground level.
        Returns <str>.
        """
        stepName = 'groundlevelfloorvegform'
        #Check if c__logiclayers returned sub-forest veg form:
        for order in ['primary', 'secondary']:
            layerResult_obj = self.v__logiclayers[order]
            if layerResult_obj.layerNum == 1:
                return layerResult_obj.vegForm_translated
        
        #c__logiclayers doesn't have a subforest layer, let's calculate:
        #PAY ATTENTION! this is a variation of c__logiclayers().

        #Replicate self.v__planttype to a local variable that is
        #not referenced, because its values might get changed.
        planttype = {k:v for k,v in self.v__planttype.items()}
        #lowForest booleans, self-describing:
        lowForest_boolList = [self.isConiferForest, self.isBroadleafForest]
        treesPresence = True in lowForest_boolList
        if treesPresence:
            if lowForest_boolList == [True, True]:
                vegForm = 'יער מעורב נמוך'
                return vegForm
            elif lowForest_boolList == [True, False]:
                vegForm = 'יער מחטני נמוך'
                return vegForm
            elif lowForest_boolList == [False, True]:
                vegForm = 'יער רחבי עלים נמוך'
                return vegForm
        elif planttype['צומח_גדות_נחלים'] >= 30:
            percent = planttype['צומח_גדות_נחלים']
            vegForm = 'צומח_גדות_נחלים'
            #translate:
            vegForm = translate(vegForm, subForestVegForm_translation)
            return vegForm
        else:
            planttype['שיחים'] += planttype['עצים'] + planttype['צומח_גדות_נחלים']
            planttype['עצים'] = 0
            planttype['צומח_גדות_נחלים'] = 0
            #The vegforms relevant for this step:
            vegForms = ['שיחים', 'בני_שיח', 'עשבוני']
            #vegForms_covers is a list of tuples: [(vegForm <str>, cover percent <int>), ...]
            #A tuple would be added only if cover percent >= 10 .
            vegForms_covers = [(vegform, planttype[vegform]) for vegform in vegForms if planttype[vegform] >= 10]
            if vegForms_covers:
                #pick the first tuple, for it's the highest hierarchy of vegForms:
                tup = vegForms_covers[0]
                vegForm = tup[0]
                #translate:
                vegForm = translate(vegForm, subForestVegForm_translation)
                return vegForm
            else:
                #No veg form of the three mentioned above has cover >= 10:
                #go to 'ללא כיסוי'.
                vegForm = 'ללא_כיסוי'
                #translate:
                vegForm = translate(vegForm, subForestVegForm_translation)
                #Add warning:
                txt = 'sub-forest layer "%s".' % vegForm
                self.notifier.add(stepName, 'warning', txt)
                return vegForm

    def c__standvegform(self, logiclayersDict):
        """
        Takes the output of c__logiclayers() method:
        - logiclayersDict: a dict of 'primary' & 'secondary' layer reselt objects.
        Calculates and returns veg form of the whole stand based on its
        calculated primary and secondary layers' veg form and layer cover.
        Returns <str>.
        """
        stepName = 'standvegform'

        primaryLayer = logiclayersDict['primary']
        secondaryLayer = logiclayersDict['secondary']

        if not primaryLayer.isForestLayer:
            return primaryLayer.vegForm_translated
        elif not secondaryLayer.isForestLayer:
            #primary layer - a forest layer
            #-and-
            #secondary layer - is not
            #
            #→return the matrix product of primary layer TIMES TWO.
            vegforms = [primaryLayer.vegForm]*2
            return standVegFormCoordinator.solve(vegforms)
        else:
            #set 3 conditions, if one or more are True → go to matrix,
            #   if all are False → return primaryLayer.vegForm.
            condition_1 = primaryLayer.vegForm == secondaryLayer.vegForm
            #2: Layercover of primary and secondary are identical or 1 level apart:
            condition_2 = abs(primaryLayer.layerCover_num - secondaryLayer.layerCover_num) <= 1
            #3: At least one of the layers is both: (1) layercover פתוח, and (2) vegform is one of the following.
            vegForms__temp = ["מחטני", "מעורב", "איקליפטוס", "יער_גדות_נחלים"]
            condition_3 = (primaryLayer.layerCover_num == 3 and primaryLayer.vegForm in vegForms__temp) or \
            (secondaryLayer.layerCover_num == 3 and secondaryLayer.vegForm in vegForms__temp)
            
            conditions = [condition_1, condition_2, condition_3]

            if True in conditions:
                #go to matrix:
                vegFormsList = [layer.vegForm for layer in [primaryLayer, secondaryLayer]]
                return standVegFormCoordinator.solve(vegFormsList)
            else:
                #→return the matrix product of primary layer TIMES TWO.
                vegforms = [primaryLayer.vegForm_translated]*2
                return standVegFormCoordinator.solve(vegforms)

            """
            #THIS IS THE OLD 
            #Both layers should have layerCover_num attribute.
            covDif = abs(primaryLayer.layerCover_num - secondaryLayer.layerCover_num)
            layers = [primaryLayer, secondaryLayer]
            if covDif >= 2:
                layers.sort(key = lambda x: x.layerCover_num, reverse = True)
                higherCoverLayer = layers[0]
                return higherCoverLayer.vegForm
            else:
                vegFormsList = [layer.vegForm for layer in layers]
                return standVegFormCoordinator.solve(vegFormsList)
            """

    def c__covtypeRel(self):
        """
        Each species code that appears in the related table
        of the stand's points, get a summation of its (proportions x [general density]).
        Each species sum is then devided by the total proportions
        sum to get the species relative percentage.
        New species proportion is then calculated by rounding
        the 10x(species relative percentage) to get an int 0-10.
        Finally, if sum of new species proportion is:
        - ==10 → return.
        - > 10 → subrtact 1 from the highest proportion.
        - < 10 → add 1 to the highest proportion.

        Returns a list of tuples = [
            (codedValue <str>, proportion <int>),
            ...
        ]
        Values returned by this method are aimed to be written into
        stand's related table.
        """
        #A dict of median values for every 'generaldensity' value:
        generalDensity_medians = {
            None: 0,
            "אין עצים": 0,
            "לא רלוונטי": 5,
            "1-10": 5,
            "11-20": 15,
            "21-40": 30,
            "41-60": 50,
            "61-100": 80,
            "מעל  100": 100,
        }
        #A dict that holds codes and sums {codedValue: sum[proportion x point density]}.
        rawSums = {}
        for point in self.points:
            generaldensity_raw = point.generaldensity
            generaldensity_median = generalDensity_medians[generaldensity_raw]
            #if median is 0 then every proportion would be multiplied by 0, so skip.
            if generaldensity_median == 0:
                continue
            for tup in point.covtype:
                codedValue = tup[0]
                proportion = int(tup[1])
                product = proportion*generaldensity_median
                #add to sum:
                if codedValue in rawSums.keys():
                    rawSums[codedValue] += product
                else:
                    rawSums[codedValue] = product
        rawTotalSum = sum(rawSums.values())

        calculatedSums = []
        for key, value in rawSums.items():
            calculatedProportion = normal_round((value/rawTotalSum)*10)
            #Add only values that are > 0 after calculation.
            if calculatedProportion > 0:
                outTuple = (key, calculatedProportion)
                calculatedSums.append(outTuple)
        
        #Sort calculatedSums by proportion in descending order:
        calculatedSums.sort(key=lambda x: x[1], reverse = True)
        calculatedTotalSum = sum([tup[1] for tup in calculatedSums])
        
        """
        if calculatedTotalSum in [0, 10]:
            return calculatedSums
        """
        if calculatedTotalSum > 10:
            #remove 1 from the species of highest proportion:
            while calculatedTotalSum > 10:
                #Modify:
                biggestTup = calculatedSums[0]
                codedValue = biggestTup[0]
                proportion = biggestTup[1]
                newProportion = proportion - 1
                biggestTup_modified = (codedValue, newProportion)
                calculatedSums[0] = biggestTup_modified
                #Re-sort:
                calculatedSums.sort(key=lambda x: x[1], reverse = True)
                #Re-calculate new sum:
                calculatedTotalSum = sum([tup[1] for tup in calculatedSums])
        elif calculatedTotalSum < 10 and calculatedTotalSum != 0:
            #add 1 to the species of highest proportion:
            while calculatedTotalSum < 10:
                #Modify:
                biggestTup = calculatedSums[0]
                codedValue = biggestTup[0]
                proportion = biggestTup[1]
                newProportion = proportion + 1
                biggestTup_modified = (codedValue, newProportion)
                calculatedSums[0] = biggestTup_modified
                #Re-sort:
                calculatedSums.sort(key=lambda x: x[1], reverse = True)
                #Re-calculate new sum:
                calculatedTotalSum = sum([tup[1] for tup in calculatedSums])
        
        #Parent to children logic:
        #Assign to nodes in root:
        root.resetValues()
        """
        #debug:
        case1 = [('3042', 2), ('1105', 5), ('1100', 3)]
        case2 = [('3042', 2), ('1204', 2), ('1200', 2), ('1105', 1), ('1103', 1), ('1100', 2)]
        case3 = [('3042', 5), ('1100', 5)]
        calculatedTotalSum = case3
        """
        for codedValue,proportion in calculatedSums:
            root.findAndSet(codedValue, proportion)
        valuableNodes = []
        findNodesAbove(root,0,valuableNodes)
        nodesToRemove = []
        valuableNodes.sort(key= lambda x: x.getLevel())
        #Find nodes that meet the criteria and assign down to children:
        for node in valuableNodes:
            if node.getLevel() == 2 and node.hasChildren():
                val_parent = node.value
                children = node.children
                valueableChildren = [node for node in children if node.value>0]
                #Based on the number of children with value:
                valueableChildren_N = len(valueableChildren)
                if valueableChildren_N == 0:
                    #could not devide by 0, go on to the next node.
                    continue
                #this function returns an integer list, len = len(children):
                valuesToAdd = specialDivide(val_parent, valueableChildren_N)
                for i, child in enumerate(valueableChildren):
                    #update values
                    child.value += valuesToAdd[i]
                #finally, set parent node value to 0
                node.value = 0
                #later it will be removed from the list
                nodesToRemove.append(node)
        for nodeToRemove in nodesToRemove:
            valuableNodes.remove(nodeToRemove)
        #turn valuableNodes from a [node, ...] → [(codedValue <str>, proportion <int>), ...]
        outList = [(node.codedValue, node.value) for node in valuableNodes]
        return outList

    def c__covtype_desc(self, covtypeList):
        """
        Takes the output of c__covtype() method:
        - covtypeList: list of tuples [
            (codedValue <str>, proportion <int>), ...
            ].
        Concatenate to the following string:
        "species name 1 - proportion, species name 2 - proportion, ..."

        -One exception for the next case:
            'שטח פתוח' proportion 10 code 9990 → return 'אין עצים'.
        """
        stepName = 'covtype_desc'
        emptyValue = 'אין עצים'
        if len(covtypeList) == 0:
            return emptyValue
        #Handle the exception of 'שטח פתוח':
        elif len(covtypeList) == 1 and int(covtypeList[0][0]) == 9990:
            return emptyValue
        else:
            #strList - ["species name 1 - proportion", "species name 2 - proportion", ...]
            strList = [] 
            for code, proportion in covtypeList:
                #try-except system to handle errors during:
                #code<str> → code<int> → name<str>
                try:
                    codeInt = int(code)
                    name = speciesDict[codeInt]
                except ValueError as e:
                    #code is not intable.
                    key = e.args[0]
                    txt = 'Unable to turn species code value (%s) into an integer.'\
                        % (key)
                    self.notifier.add(stepName, 'warning', txt)
                    continue
                except KeyError as e:
                    #Species code: not found in speciesDict.
                    #Notifty and move on.
                    key = e.args[0]
                    txt = 'Species code value (%s) is not found in: "%s".'\
                        % (key, speciesDict['__jsonFileName__'])
                    self.notifier.add(stepName, 'warning', txt)
                    continue
                else:
                    #Conditions are met:
                    #-code is intable.
                    #-species code is in species dict.
                    speciesText = "%s - %s" % (name, proportion)
                    strList.append(speciesText)
            
            if strList:
                concat = ", ".join(strList)
                return concat
            else:
                return None

    def c__covtype(self, covtypeList, logiclayersObj):
        """
        - covtypeList: list of tuples [
            (codedValue <str>, proportion <int>), ...
            ].
        - logiclayersObj: output dict of c__logiclayers {
            'primary': LayerResult,
            'secondary': LayerResult
            }
        """
        stepName = 'covtype'
        
        primaryLayer = logiclayersObj['primary']
        secondaryLayer = logiclayersObj['secondary']
        
        #### Prepare hierarchical data structure: ####
        root.resetValues()
        
        #debug:
        """
        covtypeList = [("3042", 5), ("3044", 5)]
        """
        #Set values of relevant nodes:
        for codedValue,proportion in covtypeList:
            root.findAndSet(codedValue, proportion)
        iterableNodes = root.getNodesWithValue()
        #create a result object for covtype:
        resultObj = CovtypeResult(self, speciesCompositionCoordinator, forestVegFormCoordinator)

        #LOGIC START:
        
        #check if covtype_old fields ([50098, 50099]) are:
        # "מחקר" and 9970, respectively.
        # NOTICE- "מחקר" has a DIFFERENT code from 9970.
        if self.getSelfValue([50098,50099]) == ["מחקר", "9970"]:
            resultObj.assignStudy()
            #return. that means the logic ends here.
            return resultObj

        if not primaryLayer.isForestLayer:
            """
            Assigns the layer of subforest.
            Notice: covtype can only be one of the following:
            שיחייה, בתה, עשבוני, צומח גדות נחלים
            and can not be:
            יער נמוך (any of its options)
            so, in case lrimary layer is יער נמוך the code will
            inspect further for covtype - 
            as it would do in c__logiclayers (part - 'Sub-forest inspection').
            """
            #check if layer's vegForm is יער נמוך:
            lowForest_options = [
                'יער מעורב נמוך',
                'יער מחטני נמוך',
                'יער רחבי עלים נמוך'
            ]
            isLowForest = primaryLayer.vegForm in lowForest_options

            if isLowForest:
                planttype = {k:v for k,v in self.v__planttype.items()}
                if planttype['צומח_גדות_נחלים'] >= 30:
                    covtype = 'צומח_גדות_נחלים'
                else:
                    planttype['שיחים'] += planttype['עצים'] + planttype['צומח_גדות_נחלים']
                    planttype['עצים'] = 0
                    planttype['צומח_גדות_נחלים'] = 0
                    #The vegforms relevant for this step:
                    vegForms = ['שיחים', 'בני_שיח', 'עשבוני']
                    #vegForms_covers is a list of tuples: [(vegForm <str>, cover percent <int>), ...]
                    #A tuple would be added only if cover percent >= 10 .
                    vegForms_covers = [(vegform, planttype[vegform]) for vegform in vegForms if planttype[vegform] >= 10]
                    if vegForms_covers:
                        #pick the first tuple, for it's the highest hierarchy of vegForms:
                        tup = vegForms_covers[0]
                        covtype = tup[0]
                    else:
                        #No veg form of the three mentioned above has cover >= 10:
                        #go to 'ללא כיסוי'.
                        covtype = 'ללא_כיסוי'
                
                resultObj.assignSubForest(covtype)
                return resultObj

            else:
                covtype = primaryLayer.vegForm
                resultObj.assignSubForest(covtype)
                #Check if code is None: that means it was not found in speciesHierarchy.json file.
                #and then notify:
                if (resultObj.str is not None) and (resultObj.code is None):
                    txt = "Could not find species code of %s in JSON file." % resultObj.str
                    self.notifier.add(stepName, 'warning', txt)
                #return. that means the logic ends here.
                return resultObj
        
        #check nodes' own value
        for node in iterableNodes:
            if node.value >= 8:
                resultObj.assignNode(node)
                #return. that means the logic ends here.
                return resultObj

        maxLvl = max([n.getLevel() for n in iterableNodes])
        loopAgain = True

        while loopAgain:
            #inspect
            for node in iterableNodes:
                #notice I use .sumDown() and not .value.
                if node.sumDown()>=8:
                    resultObj.assignNode(node)
                    #Notice I don't use return resultObj because
                    #IT'S NOT THE END OF THE LOGIC.
                    loopAgain = False
                        
            #go up a level only if a new loop will start later:
            # 1)Node hasn't been chosen.
            # 2)going up a level is allowed (when current maxLvl>1).
            goingUpAllowed = maxLvl>1
            if (not resultObj.assigned) and goingUpAllowed:
                #go up one level before looping again:
                loopAgain = True
                for i, node in enumerate(iterableNodes):
                    if node.getLevel() == maxLvl:
                        #fold up:
                        #1) add value to parent
                        node.parent.value += node.value
                        #2) remove value of node
                        node.value = 0
                #reset list:
                iterableNodes = root.getNodesWithValue()
                maxLvl = max([n.getLevel() for n in iterableNodes])
            else:
                loopAgain = False

        if resultObj.assigned:
            #check if it is "מעורב רחבי-עלים"
            if resultObj.mode == 'single' and resultObj.singleNode.codedValue == '2900':
                #Collect veg forms from stand's fields:
                # tmira / high / mid forest veg form.
                #notice the vegforms are taken from c__forestLayer__vegForm:
                #if it runs before it - raise an ERROR:
                if not self.forestlayerVegform_calculated:
                    errorText = "Code running order error: forest layers' veg form must be calculated before covtype."
                    arcpy.AddError(errorText)
                
                #take vegform from all forest layers (high, t, m), not only primary and secondary!
                #takes the UNtranslated vegform
                vegForms = set()
                for layerNum in [4, 3, 2]:
                    forestVegForm_raw = self.layerVegForm[layerNum]
                    if hasattr(forestVegForm_raw,'split'):
                        for vegform in forestVegForm_raw.split(','):
                            vegForms.add(vegform)
                    else:
                        continue
                """
                #old code block - takes only from priary and secondary layer:
                for layer in logiclayersObj.values():
                    if layer.layerNum in forestLayer_vegForms_numsFields.keys():
                        fieldcode = forestLayer_vegForms_numsFields[layer.layerNum]
                        forestVegForm_raw = self.getSelfValue(fieldcode)
                        for vegform in forestVegForm_raw.split(','):
                            vegForms.add(vegform)
                """
                
                #broadleafTypes is a list of possibilities sorted by order.
                #the code would take the first of any of these options
                #and return it.
                broadleafTypes = [
                    'יער_גדות_נחלים',
                    'בוסתנים_ומטעים',
                    'רחבי-עלים',
                    'חורש',
                ]
                for broadleafType in broadleafTypes:
                    if broadleafType in vegForms:
                        #specific case: change the text
                        if broadleafType == 'רחבי-עלים':
                            broadleafType = 'מעורב רחבי-עלים'
                        #return: code ends here:
                        resultObj.assignBroadleaf(broadleafType)
                        return resultObj
                
                #No item in broadleafTypes was found in vegForms.
                #vegForms list is empty or none of broadleafTypes is in it:
                #post a warning and return an errorish result.
                broadleafText = 'שגיאה רחבי-עלים'
                resultObj.assignBroadleaf(broadleafText)
                warningText = 'Could not find broadleaf type among %s' \
                % list(vegForms)
                self.notifier.add(stepName, 'warning', warningText)
                return resultObj
            else:
                return resultObj
        else:
            #resultObj hasn't been assigned yet (no node is >= 8).
            #now iterableNodes holds only species "groups" (of highest lvl).
            #logic of complementary graph:
            for n in iterableNodes:
                if n.sumDown() < 2:
                    iterableNodes.remove(n)

            #The purpose of this section is to check if 'מעורב רחבי-עלים' is
            #one of the nodes, and if so, check if can be replaced, based on 
            #the vegform RAW values of tmira, high, mid layers.
            
            #Check if "מעורב רחבי-עלים" is in iterableNodes:
            if '2900' in [n.codedValue for n in iterableNodes]:
                #Find this node's position in iterableNodes:
                broadleaf_index = [n.codedValue for n in iterableNodes].index('2900')
                #Collect veg forms from stand's fields:
                # tmira / high / mid forest veg form.
                #notice the vegforms are taken from c__forestLayer__vegForm:
                #if it runs before it - raise an ERROR:
                if not self.forestlayerVegform_calculated:
                    errorText = "Code running order error: forest layers' veg form must be calculated before covtype."
                    arcpy.AddError(errorText)
                vegForms = set()
                for layerNum in [4, 3, 2]:
                    forestVegForm_raw = self.layerVegForm[layerNum]
                    if hasattr(forestVegForm_raw,'split'):
                        for vegform in forestVegForm_raw.split(','):
                            vegForms.add(vegform)
                    else:
                        continue
                
                
                #broadleafTypes is a list of possibilities sorted by order.
                #the code would take the first of any of these options
                #and replace 'מעורב רחבי-עלים' node with it.
                broadleafTypes = [
                    'יער_גדות_נחלים',
                    'יער גדות נחלים',
                    'בוסתנים_ומטעים',
                    'בוסתנים ומטעים',
                    'רחבי-עלים', #@REQUIRES ATTENTION
                    'חורש',
                ]
                foundSubstitute = False
                for broadleafType in broadleafTypes:
                    if broadleafType in vegForms:
                        foundSubstitute = True
                        #specific case: change the text
                        if broadleafType == 'רחבי-עלים':
                            broadleafType = 'מעורב רחבי-עלים'
                        #find the node by its name in root:
                        substituteNode = Node()
                        str = broadleafType
                        str_translated = translate(str, subForestVegForm_translation)
                        substituteNode = findNodeByName(root, str_translated)
                        if not substituteNode.isEmpty():
                            #Re-construct root tree based on the species in iterable nodes.
                            #However, this time every iterableNode has its OWN value,
                            #and not a sumDown of its children.
                            #A list of tuples [(codedValue, proportion)]
                            tupList = []
                            for i, node in enumerate(iterableNodes):
                                isSubstitute = i==broadleaf_index
                                if isSubstitute:
                                    #Combine the new coded value, and the previous sumDown().
                                    codedValue = substituteNode.codedValue
                                    proportion = node.sumDown()
                                    tupList.append((codedValue, proportion))
                                else:
                                    codedValue = node.codedValue
                                    proportion = node.sumDown()
                                    tupList.append((codedValue, proportion))
                            
                            root.resetValues()
                            for codedValue,proportion in tupList:
                                root.findAndSet(codedValue, proportion)
                            
                            #re-construct iterableNodes list:
                            iterableNodes = root.getNodesWithValue()
                        else:
                            txt = 'Could not locate %s in JSON file.' % str_translated
                            self.notifier.add(stepName, 'warning', txt)

                        #Substitution finished - stop this for-loop:
                        break
                if not foundSubstitute:
                    #One of iterableNodes is 'מעורב רחבי עלים', and no substitute was
                    #found in veg forms of tmira \ high \ mid layers.
                    #add warning:
                    txt = "Could not find substitute for '%s' in stand's veg forms of layers tmira \\ high \\ mid." % \
                    iterableNodes[broadleaf_index].name
                    #suspend warning: (development section #5)
                    #self.notifier.add(stepName, 'warning', txt)

            if len(iterableNodes) == 1:
                resultObj.assignNode(iterableNodes[0])
                return resultObj
            elif len(iterableNodes) == 2:
                resultObj.assignNodes([iterableNodes[0], iterableNodes[1]])
                return resultObj
            elif len(iterableNodes) > 2:
                #That means~~ len(iterableNodes) > 2
                #sort descending by sumDown():
                iterableNodes.sort(key=lambda x: x.sumDown(), reverse=True)
                if iterableNodes[1].sumDown() > iterableNodes[2].sumDown():
                    #Second species group > third:
                    resultObj.assignNodes([iterableNodes[0], iterableNodes[1]])
                    return resultObj
                else:
                    #Second == third
                    if iterableNodes[0].sumDown() > iterableNodes[1].sumDown():
                        #First > second (and third)
                        if '1000' in [n.codedValue for n in iterableNodes[1:]]:
                            #בקבוצות הקטנות (לא הראשונה) יש מחטני
                            mahtaniNode_index = [n.codedValue for n in iterableNodes].index('1000')
                            mahtaniNode = iterableNodes[mahtaniNode_index]
                            resultObj.assignNodes([iterableNodes[0], mahtaniNode])
                            return resultObj
                        else:
                            #בקבוצות הקטנות (לא הראשונה) אין מחטני
                            resultObj.assignNodes([iterableNodes[0], iterableNodes[1]])
                            return resultObj
                    else:
                        #First == second == third
                        resultObj.assignNodes([iterableNodes[0], iterableNodes[1]])
                        return resultObj
        
        #In case an unpredicted situation happened, return a default result obj and warn.
        self.warnings.append("Could not determine species composition.")
        resultObj.str = "Could not determine."
        return resultObj

    def c__forestagecomposition_old(self):
        """
        Must be callued after c__logiclayers - in order to inspect primarylayer.
        If stand's primary layer is grund level (layerNum == 1): return 'אין קומת עצים'.
        else:
        Then takes a list of values from forest age composition,
        omits undesired values, and returns the maximal value.
        If after omission the list is empty → returns None.
        """
        #Part 1
        groundLevelDefault = 'אין קומת עצים'
        primaryLayer = self.v__logiclayers['primary']
        if primaryLayer.layerNum == 1:
            return groundLevelDefault
        
        #Part 2
        rawValues = self.getRelatedValues('sp', 40019)
        #domainValues - every possible result from the field sorted.
        domainValues = [
            None,
            'אחר (פרט בהערות)',
            'חד שכבתי',
            'דו שכבתי',
            'רב שכבתי',
        ]
        indexList = [domainValues.index(rv) for rv in rawValues]
        #indexes to be removed: None or אחר
        for indexToRemove in [0, 1]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        if len(indexList) > 0:
            return domainValues[max(indexList)]
        else:
            return None

    def c__forestagecomposition(self):
        """
        Takes all the values from fields "Tmira/high/mid layer cover",
        ommits any value that is below "פזור",
        returns according to the amount of values left:
        - 0 values are "פזור" or above → "אין קומת גובה"
        - 1...
        - 2...
        - 3 → "רב שכבתי"
        Must be callued after c__forestLayer__layerCover has ran, and its values were written.
        """
        #indexed list of options to return:
        optionsToReturn = [
            "אין קומת עצים",
            "חד שכבתי",
            "דו שכבתי",
            "רב שכבתי",
        ]
        layerCoverKeys = list(layerCover_table1.keys())
        thrasholdIndex = 2

        rawValues = self.getSelfValue([50047,50051,50055])
        #Keep only values that can be indexed later.
        validValues = []
        for rawValue in rawValues:
            if rawValue in layerCoverKeys:
                validValues.append(rawValue)
        
        indexedValues = [layerCoverKeys.index(v) for v in validValues]
        N_valuesAboveThreshold = len([index_ for index_ in indexedValues if index_ >= thrasholdIndex])
        return optionsToReturn[N_valuesAboveThreshold]

    def c__generaldensity(self):
        """
        Takes a list of values from general density,
        omits undesired values, and returns the ceil(average()) of values.
        - If after omission the list is empty → return None.
        - If the list contains None → warn + return None.
        - If the list contains only 'לא רלוונטי' → return 'לא רלוונטי'.
        - Else → each value gets an ordinal index, then averaged, then return
                 the category.
        """
        stepName = 'generaldensity'
        rawValues = self.getRelatedValues('sp', 40020)
        #domainValues - every possible result from the field sorted.
        domainValues = [
            None,
            "לא רלוונטי",
            "אין עצים",
            "1-10",
            "11-20",
            "21-40",
            "41-60",
            "61-100",
            "מעל  100",
        ]
        if None in rawValues:
            #Warn and return None
            fName = fieldsDict[40020].name
            fAlias = fieldsDict[40020].alias
            txt = 'Found <null> in related sekerpoints field "%s", "%s".' % (fName, fAlias)
            self.notifier.add(stepName, 'warning', txt)
            return None
        elif removeDup(rawValues) == [domainValues[1]]:
            #All the rawValues are "לא רלוונטי": return it
            return domainValues[1]
        else:
            indexList = []
            for rawValue in rawValues:
                if rawValue in domainValues:
                    indexList.append(domainValues.index(rawValue))
                else:
                    #Found a value that is not one of the possibilities.
                    #Handle in a similar way to None (see above).
                    #Warn and return None
                    fName = fieldsDict[40020].name
                    fAlias = fieldsDict[40020].alias
                    txt = 'Found invalid value "%s" in related sekerpoints field "%s", "%s".' % (rawValue, fName, fAlias)
                    self.notifier.add(stepName, 'warning', txt)
                    return None
            if indexList:
                #This is the main logic: round up of the indices.
                chosenIndex = math.ceil(average(indexList))
                return domainValues[chosenIndex]
            else:
                return None

    def c__standdensity(self, generalDensity):
        """
        Must be called after general density.
        Takes a list of values from stand density,
        omits undesired values, and returns the ceil(average()) of values.
        If after omission the list is empty → returns None.
        Stand density result could be affected by general density in two ways:
        1) If general density is 'אין עצים' / 'לא רלוונטי':
            → notify and return an identical value.
        2) If general density < stand density:
            → nofity and return stand density.
        """
        #domainValues - every possible result from the field sorted.
        domainValues = [
            None,
            "לא רלוונטי",
            "אין עצים",
            "1-10",
            "11-20",
            "21-40",
            "41-60",
            "61-100",
            "מעל  100",
        ]

        stepName = 'standdensity'
        generalDensity_index = domainValues.index(generalDensity)

        #Check 1 (see method description):
        if generalDensity in [domainValues[1], domainValues[2]]:
            #txt = 'stand density was auto-assigned to be as general density (%s).'\
            #% generalDensity
            #self.notifier.add(stepName, 'warning', txt)
            return generalDensity


        rawValues = self.getRelatedValues('sp', 40021)
        
        indexList = [domainValues.index(rv) for rv in rawValues]
        #indexes to be removed: לא רלוונטי or None
        for indexToRemove in [0, 1]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        if len(indexList) > 0:
            chosenIndex = math.ceil(average(indexList))
            #Check 2 (see method description):
            if chosenIndex <= generalDensity_index:
                return domainValues[chosenIndex]
            else:
                txt = 'stand density > general density. stand density was auto-assigned to be as general density (%s).'\
                % generalDensity
                self.notifier.add(stepName, 'warning', txt)
                return generalDensity
        else:
            return None

    def c__coniferforestage(self):
        """
        Calculate conifer forest age based of points' value of the field
        with the same name.
        #@ comment!
        """
        stepName = 'coniferforestage'
        rawValues = self.getRelatedValues('sp', 40022)
        domainValues = {
            #value <str>: (avg <float>, max <int>),
            None: (None, None),
            "לא רלוונטי": (None, None),
            "רב גילי": (None, None),
            "בהקמה (1)": (1.0, 1),
            "בהקמה (2)": (2.0, 2),
            "בהקמה (3)": (3.0, 3),
            "בהקמה (4)": (4.0, 4),
            "בהקמה (5)": (5.0, 5),
            "חדש (6-10)": (8.0, 10),
            "צעיר (11-15)": (13.0, 15),
            "צעיר (16-20)": (18.0, 20),
            "מתבגר (21-25)": (23.0, 25),
            "מתבגר (26-30)": (28.0, 30),
            "בוגר (31-40)": (35.5, 40),
            "בוגר (41-50)": (45.5, 50),
            "בוגר (51-60)": (55.5, 60),
            "ותיק (61-75)": (68.0, 75),
            "ותיק (76-90)": (83.0, 90),
            "ותיק (91-105)": (98.0, 105),
        }
        #Check if there are valuable values:
        notValueableValues = [] #None / לא רלוונטי / רב גילי
        valueableValues = [] #all other values
        for rawValue in rawValues:
            if rawValue not in domainValues.keys():
                #Value is not a valid option → warn and skip.
                txt = 'Invalid value in "ConiferForestAge" - "%s". stands %s: %s.' % (rawValue, self.FC.oidFieldName, self.id)
                self.notifier.add(stepName, 'warning', txt)
                continue
            elif domainValues[rawValue][0]:
                #e.g it's not None.
                valueableValues.append(rawValue)
            else:
                notValueableValues.append(rawValue)
        #Valueable values take over anything else:
        if valueableValues:
            avgs = [domainValues[value][0] for value in valueableValues]
            calculatedValue = math.ceil(average(avgs))
            #a list of tuples [(maxVal of category, category name), ...]:
            backwardsList = [(v[1],k) for k,v in domainValues.items()]
            #remove None values from backwardsList:
            validBackwardsList = []
            for tup in backwardsList:
                if tup[0] is not None:
                    validBackwardsList.append(tup)
            return toCategory(calculatedValue, validBackwardsList, None)
        elif notValueableValues:
            hierarchy = [
                "רב גילי",
                "לא רלוונטי",
                None
            ]
            for value in hierarchy:
                if value in notValueableValues:
                    return value
            #Shouldn't get here, but just to avoid bugs...
            return None
        else:
            #Both lists are empty:
            return None

    def c__relativedensity_old(self, coniferforestage, generaldensity, beitgidul):
        """
        Based on calculation performed in previous project (August 2021)
        (3.3.2-4 → 3.3.4 Density).
        Inputs:
        - coniferforestage: result of c__coniferforestage().
        - generaldensity: result of c__generaldensity().
        - beitgidul: a tool input, can be one of three.
        """
        #Variables:
        coniferforestage_domainValues = {
            #Dilul index for any possible result of coniferforestage:
            #coniferforestage: dilul index (or Null if necessary).
            None:  None,
            "לא רלוונטי":  None,
            "רב גילי":  None,
            "בהקמה (1)":  0,
            "בהקמה (2)":  0,
            "בהקמה (3)":  0,
            "בהקמה (4)":  0,
            "בהקמה (5)":  0,
            "חדש (6-10)":  0,
            "צעיר (11-15)":  1,
            "צעיר (16-20)":  1,
            "מתבגר (21-25)":  2,
            "מתבגר (26-30)":  2,
            "בוגר (31-40)":  2,
            "בוגר (41-50)":  2,
            "בוגר (51-60)":  2,
            "ותיק (61-75)":  2,
            "ותיק (76-90)":  2,
            "ותיק (91-105)":  2,
        }
        beitgidulList = [
            "ים-תיכוני",
            "ים-תיכוני יבש",
            "צחיח-למחצה"
        ]
        treesToDunamTable = [
            #dilul 1 (dilul index = 0)
            [70.0, 60.0, 50.0],
            #dilul 2 (dilul index = 1)
            [45.0, 40.0, 35.0],
            #dilul 3 (dilul index = 2)
            [30.0, 25.0, 20.0]
        ]
        densityTuples = {
            #each value gets a tuple of (min, max).
            None: None,
            "לא רלוונטי": None,
            "אין עצים": (0,0),
            "1-10": (1,10),
            "11-20": (11,20),
            "21-40": (21,40),
            "41-60": (41,60),
            "61-100": (60,100),
            "מעל  100": (101, 115),
        }
        averages_backwards = [
            #enables you to go back to categoty.
            #(maximum value of class, class name)
            (0.07, "לא רלוונטי"),
            (0.75, "נמוכה"),
            (1.1, "מותאמת או נמוכה"),
            (1.3, "מותאמת או גבוהה"),
            (2.0, "גבוהה"),
            (3.5, "גבוהה מאוד")
        ]
        defaultReturnValue = "לא רלוונטי"

        #Procrss:
        dilul_index = coniferforestage_domainValues[coniferforestage]
        if dilul_index is None:
            return defaultReturnValue
        beitgidul_index = beitgidulList.index(beitgidul)
        treesToDunam = treesToDunamTable[dilul_index][beitgidul_index]
        if generaldensity not in densityTuples.keys():
            warningMessage = 'Invalid value of generaldensity: "%s". stands %s: %s.' % (generaldensity, self.FC.oidFieldName, self.id)
            arcpy.AddWarning(warningMessage)
            return None
        #a tuple of (min, max):
        densityTuple = densityTuples[generaldensity]
        if densityTuple is None:
            return defaultReturnValue
        else:
            ranks = [float(x)/treesToDunam for x in densityTuple]
            ranksMean = average(ranks)
            return toCategory(ranksMean, averages_backwards, defaultReturnValue)

    def c__relativedensity(self, agegroup, generaldensity, beitgidul):
        """
        Method takes string inputs and inserts them as parameters for
        a 3-dimensional matrix.
        """
        stepName = 'relativedensity'
        #@Consider evaluating the values of each input before passing on.
        #remember that the matrix coordinator has a validation mechanism.
        tup = (
            beitgidul,
            agegroup,
            generaldensity
        )
        matrix_solution = relativeDensityKeyCoordinator.solve(tup)
        if matrix_solution['errorMessage']:
            #That means something went wrong and a warning should be raised.
            txt = matrix_solution['errorMessage']
            self.notifier.add(stepName, 'warning', txt)
        
        return matrix_solution['value']

    def c__forestLayer__layerCover(self, layerNum):
        """
        Takes all the layer cover averages from layers of layerNum, 
        among all the sekerpoints that belong to this stand.
        Remove None values, average them, and convert it to category.
        Returns layer cover category <str>.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        """
        #Convert layerNum to layer short text, a key of point.layers dict.
        layerShort = layerToShortText[layerNum]
        layerCover_averages = [point.layers[layerShort].layerCover_avg for point in self.points]
        #There might be None objects in layerCover_averages list:
        #replace them with 0:
        while None in layerCover_averages:
            i = layerCover_averages.index(None)
            layerCover_averages[i] = layerCover_table1["אין"][1]
        #while None in layerCover_averages: layerCover_averages.remove(None)
        if layerCover_averages:
            #e.g., len>0
            layerCover_average = average(layerCover_averages)
            layerCover_category = toCategory(
                layerCover_average,
                layerCover_table1_backwardsList,
            )
            return layerCover_category
        else:
            return None

    def c__forestLayer__species(self, layerNum):
        """
        Takes all the species codes from layers of layerNum, among all
        the sekerpoints that belong to this stand.
        Finds the 3 most frequent species codes, matches them with
        their species names.
        returns a dict of the 3 most frequent codes and names
        ready to be used as string to applied as field value.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        """
        #Convert layerNum to layer short text, a key of point.layers dict.
        layerShort = layerToShortText[layerNum]
        #speciesCodes_lists is a list of lists.
        speciesCodes_lists = [point.layers[layerShort].speciesCodes for point in self.points]
        #Turn speciesCodes_lists (list of lists) into a list,
        #that can have duplications:
        speciesCodes_list = flatten(speciesCodes_lists)
        #Sort by descending frequency of appearance, and remove duplications:
        speciesCodes = freqSorted(speciesCodes_list)
        #Match name for every code:
        #notice: species codes were verified during the creation of point's
        #forest layers.
        speciesNames = [speciesDict[c] for c in speciesCodes]
        #return a dict of top 3 codes and names, and concatenate using ",":
        outdict = {
            'codes': ','.join([str(x) for x in speciesCodes[:3]]),
            'names': ','.join([str(x) for x in speciesNames[:3]])
        }
        return outdict

    def c__forestLayer__vegForm(self, layerNum):
        """
        Take all vegForms and cover from layerNum,
        sum cover for every vegForm that appeared in the points.
        With the list of vegForms and calculated cover, go through
        a decision tree and return final veg form <str>.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        """
        #coverToOmit: "אין" is unwanted for the logic.
        coverToOmit = 'אין'
        #Convert layerNum to layer short text, a key of point.layers dict.
        layerShort = layerToShortText[layerNum]
        #Collect cover averages:
        #vegForms_coversAvgs - {vegForm <str>: [ceil(cover averages / N_vegForms), ...] <list of int>, ...}
        vegForms_coversAvgs = {}
        for point in self.points:
            layer = point.layers[layerShort]
            if layer.isValid:
                numerator = layer.layerCover_avg
                #The length of vegForms cannot be zero for valid layers.
                denominator = len(layer.vegForms)
                quotient = math.ceil(numerator/denominator)
                for vegForm in layer.vegForms:
                    if vegForm in vegForms_coversAvgs.keys():
                        vegForms_coversAvgs[vegForm].append(quotient)
                    else:
                        vegForms_coversAvgs[vegForm] = [quotient]
        
        #vegForms_info = [(vegform <str>, cover <str>, ordered num <int>), ...]
        vegForms_info = []
        for vegForm, coverAvgs in vegForms_coversAvgs.items():
            avg = math.ceil(sum(coverAvgs)/self.N_points)
            cover = toCategory(avg, layerCover_table1_backwardsList)
                #Don't include 'אין' cover.
            if cover == coverToOmit: continue
            coverOrder = layerCover_table1[cover][0]
            vegForms_info.append((vegForm, cover, coverOrder))
        
        #decision tree: second page in 'סכמת איחוד תצורות צומח לקומות היער_151022.pptx'
        if len(vegForms_info) == 0:
            return None
        #Hence, len(vegForms_info) > 0.
        #Filter vegForms_info into two lists:
        # -vegForms_above1: for cover > 1 (זניח):
        # -vegForms_cover1: for cover == 1.
        vegForms_above1 = [tup for tup in vegForms_info if tup[2]>1]
        vegForms_cover1 = [tup for tup in vegForms_info if tup[2]==1]
        #sort by cover's orderedNum (descending order):
        vegForms_above1.sort(key= lambda x: x[2], reverse= True)
        vegForms_cover1.sort(key= lambda x: x[2], reverse= True)

        if vegForms_above1:
            if len(vegForms_above1) == 1:
                vegForm = vegForms_above1[0][0]
                return vegForm
            elif (vegForms_above1[0][2] - vegForms_above1[1][2]) >= 2:
                #Compare the ordered num of the 1st and 2nd veg forms:
                #True when orderen num of 1st is greater of the 2nd by
                #at least 2.
                vegForm = vegForms_above1[0][0]
                return vegForm
            elif 'יער_גדות_נחלים' in [tup[0] for tup in vegForms_above1]:
                #One of these vegforms is 'יער_גדות_נחלים':
                vegForm = 'יער_גדות_נחלים'
                return vegForm
            elif 'בוסתנים_ומטעים' in [tup[0] for tup in vegForms_above1]:
                #One of these vegforms is 'בוסתנים_ומטעים':
                vegForm = 'בוסתנים_ומטעים'
                return vegForm
            else:
                #Return all the veg forms in a string seperated by commas:
                vegForms = [tup[0] for tup in vegForms_above1]
                return ','.join(vegForms)
                #@ deprecated:
            """
            #2 last conditions: Go to matrixes, with or w/o 'מחטני'.
            elif 'מחטני' in [tup[0] for tup in vegForms_above1]:
                #one of the vegForms in vegForms_above1 is'מחטני'.
                #others = vegForm tuples other than 'מחטני'.
                others = [tup for tup in vegForms_above1 if tup[0] != 'מחטני']
                vegForm_other = others[0][0]
                vegForm = forestVegFormCoordinator.solve(['מחטני', vegForm_other])
                return vegForm
            else:
                vegForm_0 = vegForms_above1[0][0]
                vegForm_1 = vegForms_above1[1][0]
                vegForm = forestVegFormCoordinator.solve([vegForm_0, vegForm_1])
                return vegForm
            """
        else:
            #e.g., len(vegForms_cover1) > 0.
            if len(vegForms_cover1) == 1:
                vegForm = vegForms_cover1[0][0]
                return vegForm
            else:
                #Return all the veg forms in a string seperated by commas:
                vegforms = [tup[0] for tup in vegForms_cover1]
                return ','.join(vegforms)
                #@ deprecated:
                if 'מחטני' in [tup[0] for tup in vegForms_cover1]:
                    #one of the vegForms in vegForms_cover1 is'מחטני'.
                    #others = vegForm tuples other than 'מחטני'.
                    others = [tup for tup in vegForms_cover1 if tup[0] != 'מחטני']
                    vegForm_other = others[0][0]
                    vegForm = forestVegFormCoordinator.solve(['מחטני', vegForm_other])
                    return vegForm
                else:
                    #len(vegForms_cover1) > 1
                    vegForm_0 = vegForms_cover1[0][0]
                    vegForm_1 = vegForms_cover1[1][0]
                    vegForm = forestVegFormCoordinator.solve([vegForm_0, vegForm_1])
                    return vegForm

    def c__planttype(self):
        """
        Calculates plant type cover.
        Related points must be queried in advance for their plant type
        dictionary based on each point's related table.
        Returns a dictionary of every plant type & its percent:
        {plant type 1 <int>: percent <int>, ...}
        """
        stepName = 'planttype'
        #Empty output dictionary:
        plantTypeDict = {
            "צומח_גדות_נחלים": 0,
            "עצים": 0,
            "שיחים": 0,
            "בני_שיח": 0,
            "עשבוני": 0,
            "ללא_כיסוי": 0,
            "מינים_פולשים": 0
        }

        if self.N_points == 0:
            #Because the rest of the code requires devision by self.N_points.
            return plantTypeDict
        
        #Sum all values of each key to plantDict:
        for point in self.points:
            for k, v in point.planttype.items():
                try:
                    plantTypeDict[k] += v
                except KeyError as e:
                    #Species code: not found in speciesDict.
                    #Notifty and move on.
                    key = e.args[0]
                    txt = 'Plant type (%s) is not found in: %s.'\
                        % (key, list(plantTypeDict.keys()))
                    self.notifier.add(stepName, 'warning', txt)
        
        #outputDict is a dictionary of values of plantTypeDict
        #after they have been devided by self.N_points and rounded to
        #the closest 10.
        outputDict = {}
        for k, v in plantTypeDict.items():
            avg = v/self.N_points
            roundedAverage = normal_round(avg/10)*10
            #Notify if value is above 100.
            if roundedAverage > 100:
                txt = f'Plant type percent > 100%: {k} - {roundedAverage}.'
                self.notifier.add(stepName, 'warning', txt)
            outputDict[k] = roundedAverage
        return outputDict

    def c__planttype_desc(self, planttypeDict):
        """
        Takes the output of c__planttype() method:
        - planttypeDict: dict with every plant type and its percent:
            {plant type 1 <str>: percent <int>, ...}
        Returns a concatenated <str> as follows:
        "plant type 1 - percent, plant type 2 - percent, ..."
        Every plant type text will be replaced by a short version
        according to a dictionary. 
        Not sorted by percent value.
        """
        planttypeShortVersions = {
            "עצים": "עצ",
            "שיחים": "שיח",
            "בני_שיח": "ב.שיח",
            "עשבוני": "עשב",
            "ללא_כיסוי": "ל.כ",
            "צומח_גדות_נחלים": "צ.ג.נ",
            "מינים_פולשים": "מ.פ"
        }
        tupList = [(k,v) for k,v in planttypeDict.items()]
        #tupList.sort(key=lambda x: x[1], reverse = True)
        #strList = ["plant type 1 - percent", "plant type 2 - percent"]
        strList = []
        for tup in tupList:
            #insert the shorter version of covtype string:
            planttype = planttypeShortVersions[tup[0]]
            proportion = tup[1]
            txt = "%s - %s" % (planttype, proportion)
            strList.append(txt)
        
        if strList:
            concat = ", ".join(strList)
            return concat
        else:
            return None

    def c__subSpecies(self, codesFieldCode):
        """
        Takes values from the codes field of the seker point, and 
        returns a dict of the 3 most frequent codes and names
        ready to be used as string to applied as field value.
        """
        rawValues = self.getRelatedValues('sp', codesFieldCode)
        IDs = self.getRelatedValues('sp', 40000) #the ID field Code.

        codes = []
        for i in range(len(rawValues)):
            #rawValue is either a string of codes ("1111,2222") or a None.
            rawValue = rawValues[i]
            point_id = IDs[i]
            if rawValue is None:
                continue
            else:
                #split with ',':
                rawValue_splitted = rawValue.split(',')
                #add to codes if value is intable
                for x in rawValue_splitted:
                    if isIntable(x):
                        if int(x) in speciesDict.keys():
                            codes.append(int(x))
                        else:
                            warningMessage = "Species code '%s' wasn't found in species list. point id: %s." % (x, point_id)
                            arcpy.AddWarning(warningMessage)
                            continue
                    else:
                        warningMessage = "Species code '%s' failed to be turned into an integer. point id: %s." % (x, point_id)
                        arcpy.AddWarning(warningMessage)
                        continue
        
        #get a list of codes w/o duplications sorted by frequency in descending order:
        codes_freq = freqSorted(codes)
        #match name for every code:
        names_freq = [speciesDict[c] for c in codes_freq]
        #return a dict of top 3 codes and names, and concatenate using ",":
        outdict = {
            'codes': ','.join([str(x) for x in codes_freq[:3]]),
            'names': ','.join([str(x) for x in names_freq[:3]])
        }
        return outdict

    def c__presenceconifer(self):
        """
        Takes a list of values from presence conifer,
        omits undesired values, and returns the ceil(average()) of values.
        If after omission the list is empty → returns None.
        """
        rawValues = self.getRelatedValues('sp', 40055)
        #domainValues - every possible result from the field sorted.
        domainValues = [
            None,
            "אין",
            "1-20",
            "21-50",
            "51-100",
            "מעל 100",
        ]
        validValues = []
        for rawValue in rawValues:
            if rawValue in domainValues:
                validValues.append(rawValue)
            else:
                warningMessage = 'Invalid value of presenceconifer: %s. stands %s: %s.' % (rawValue, self.FC.oidFieldName, self.id)
                arcpy.AddWarning(warningMessage)
        #convert values to their index:
        indexList = [domainValues.index(value) for value in validValues]
        #indexes to be removed: 'None' only.
        for indexToRemove in [0]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        if indexList:
            chosenIndex = math.ceil(average(indexList))
            return domainValues[chosenIndex]
        else:
            return None

    def c__presencebroadleaf(self):
        """
        Takes a list of values from presence broadleaf,
        omits undesired values, and returns the ceil(average()) of values.
        If after omission the list is empty → returns None.
        """
        rawValues = self.getRelatedValues('sp', 40057)
        #domainValues - every possible result from the field sorted.
        domainValues = [
            None,
            "אין",
            "1-5",
            "6-10",
            "11-20",
            "מעל 20",
        ]
        validValues = []
        for rawValue in rawValues:
            if rawValue in domainValues:
                validValues.append(rawValue)
            else:
                warningMessage = 'Invalid value of presencebroadleaf: %s. stands %s: %s.' % (rawValue, self.FC.oidFieldName, self.id)
                arcpy.AddWarning(warningMessage)
        #convert values to their index:
        indexList = [domainValues.index(value) for value in validValues]
        #indexes to be removed: 'None' only.
        for indexToRemove in [0]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        if indexList:
            chosenIndex = math.ceil(average(indexList))
            return domainValues[chosenIndex]
        else:
            return None

    def c__presencetype(self, fieldCode):
        """
        Takes values from presenceconifertype / presencebroadleaftype <str>,
        remove duplications, merges and returns an inclusive value.
        "נטיעה,התחדשות_טבעית" is 'a joker' that takes over enything else,
        a combination of the other two possibilities will return a joker too.
        """
        rawValues = self.getRelatedValues('sp', fieldCode)
        optionalValues = [
            #these are not domains
            None,
            "נטיעה",
            "התחדשות_טבעית",
            "נטיעה,התחדשות_טבעית"
        ]
        jokerValue = optionalValues[3]
        
        #first check if jokerValue is one of the rawValues → then return it:
        if jokerValue in rawValues:
            return jokerValue

        #make sure all values are valid:
        validValues = []
        for rawValue in rawValues:
            if rawValue in optionalValues:
                validValues.append(rawValue)
            else:
                warningMessage = 'Invalid value of %s: %s. stands %s: %s.' % (fieldsDict[fieldCode].name, rawValue, self.FC.oidFieldName, self.id)
                arcpy.AddWarning(warningMessage)
        
        #now all values are valid, convert to indexes:
        indexList = [optionalValues.index(value) for value in validValues]
        #indexes to be removed: None only (index = 0).
        while 0 in indexList:
            indexList.remove(0)
        
        if len(indexList) == 0:
            return None

        #remove duplications
        indexList = removeDup(indexList)
        #Now we have a list of indexes that can contain 1, 2 or both!
        #if it had index 3 → it's a joker, would return it in the beginning.
        #if it had index 0 → it's a None, removed it before.
        #decide on an option:
        if (1 in indexList) and (2 in indexList):
            return jokerValue
        elif 1 in indexList:
            return optionalValues[1]
        elif 2 in indexList:
            return optionalValues[2]

    def c__treeharmindex(self, fieldCode):
        """
        Not to be confused with treeharm field.
        Takes values of harm rank from one of the fields:
            -DeadTreesPercent
            -InclinedTreesPercent
            -BrokenTreesPercent
            -BrurntTreesPercent
        converts to indexes, average them, round up and return the matching category.
        """
        fieldName = fieldsDict[fieldCode].name
        stepName = "tree harm index: %s" % fieldName
        rawValues = self.getRelatedValues('sp', fieldCode)
        domainValues = {
            #value <str>: (ceil of avg <int>, max <int>),
            "אין": (0, 0),
            "זניח (3%-0%)": (2, 3),
            "מועט (10%-3%)": (7, 10),
            "בינוני (33%-10%)": (22, 33),
            "גבוה (66%-33%)": (50, 66),
            "גבוה מאוד (מעל 66%)": (88, 100),
        }
        #backwardsList for toCategory function.
        #(maxVal of category, category name)
        backwardsList = [(v[1],k) for k,v in domainValues.items()]
        
        #make sure all values are valid:
        validValues = []
        for rawValue in rawValues:
            if rawValue in domainValues.keys():
                validValues.append(rawValue)
            elif rawValue is None:
                #A notification is not necessary.
                continue
            else:
                #value is not valid or none → notify as warning.
                txt = "Invalid value in point's field '%s': %s." % (fieldName, rawValue)
                self.notifier.add(stepName, 'warning', txt)
        
        if validValues:
            #e.g., if len>0:
            #Convert value list [<str>, ...] → category-average list [<int>, ...]:
            averagesList = [domainValues[v][0] for v in validValues]
            calculatedValue = math.ceil(average(averagesList))
            category = toCategory(calculatedValue, backwardsList)
            return category
        else:
            #len == 0:
            #because average function devides by zero.
            return None

    def c__treeharm(self, treeharmList):
        """
        Takes 4 outputs of c__treeharmindex, convets each one to
        its category's average, sums, and returns category <str> of
        min(sum(), 100).
        """
        stepName = "treeharm"
        #constants from c__treeharmindex:
        domainValues = {
            #value <str>: (ceil of avg <int>, max <int>),
            "אין": (0, 0),
            "זניח (3%-0%)": (2, 3),
            "מועט (10%-3%)": (7, 10),
            "בינוני (33%-10%)": (22, 33),
            "גבוה (66%-33%)": (50, 66),
            "גבוה מאוד (מעל 66%)": (88, 100),
        }
        #backwardsList for toCategory function.
        #(maxVal of category, category name)
        backwardsList = [(v[1],k) for k,v in domainValues.items()]

        #notice: items of treeharmList can be either one of domainValues.keys() or None.
        #Remove None from treeharmList:
        while None in treeharmList:
            treeharmList.remove(None)
        #convert category to ceil of avg:
        averagesList = [domainValues[category][0] for category in treeharmList]
        #Sum. if len(averagesList) == 0: sum = 0.
        averagesSum = sum(averagesList)
        #Notify in case averagesSum > 100:
        if averagesSum>100:
            txt = 'sum of harms averages > 100. Items: %s' % str(treeharmList)
            self.notifier.add(stepName, 'warning', txt)
        #convert to categoryand return:
        category = toCategory(min(averagesSum, 100), backwardsList)
        return category

    def c__vitalforest(self):
        """
        For each category of forest defect that appears,
        average the ceil(avg()) of the category values and get
        the category this average fits into.
        Returns a dict of {forest defect <str>: percent impact <str>, ...}.
        """
        #defectsCategories is the dict to be returned
        #defectsCategories = {forest defect <str>: percent impact <str>}
        defectsCategories = {}
        stepName = 'vital forest'
        defects_domainValues = [
            None,
            'עיכוב בהתפתחות העצים',
            'יחס צמרת קטן',
            'גזעים דקים ביחס לגובה',
            'כותרת דלילה',
            'שטח שרובו שרוף (ללא התחדשות עדיין)',
            'התייבשות החלק העליון בכותרת',
            'הצהבת כותרת (כלורוזיס)',
            'רקבונות',
            'קילופים או פצעי גיזום גדולים',
            'ריבוי גזעים (באיקליפטוס, ר"ע מינים מסוימים)',
            'אחר (פרט בהערות)',
        ]
        elseValue = defects_domainValues[len(defects_domainValues)-1] #(last)
        #defectsAverages is the object to hold the summation of percents averages
        #for every defect.
        #{forest defect <str>: averages [<int>, ...]}
        defectsAverages = {} 
        percent_domainValues = {
            #value <str>: (ceil of avg <int>, max <int>),
            "אין": (0, 0),
            "זניח (3%-0%)": (2, 3),
            "מועט (10%-3%)": (7, 10),
            "בינוני (33%-10%)": (22, 33),
            "גבוה (66%-33%)": (50, 66),
            "גבוה מאוד (מעל 66%)": (88, 100),
        }
        #backwardsList for toCategory function.
        #(maxVal of category, category name)
        backwardsList = [(v[1],k) for k,v in percent_domainValues.items()]
        
        #Sum the percents of all related rows of all points:
        for point in self.points:
            for tup in point.vitalforest:
                #tup - a tuple that represents a row in vital forest related table.
                defectCategory = tup[0]
                defectPercent = tup[1]
                #If defectPercent is None: not an "invalid value",
                #nothing to add, though, skip to next tuple:
                if defectCategory is None: continue
                #Two conditions for validity of values:
                validity_conditions = [
                    defectCategory in defects_domainValues,
                    defectPercent in percent_domainValues.keys()
                ]
                if False in validity_conditions:
                    #Values are not valid, add warning and skip.
                    txt = "Point %s: %s. Invalid value: (%s, %s)." % (point.FC.oidFieldName, point.id, defectCategory, defectPercent)
                    self.notifier.add(stepName, 'warning', txt)
                    continue
                else:
                    #values are valid, add categoryAverage to category:
                    categoryAverage = percent_domainValues[defectPercent][0]
                    if defectCategory in defectsAverages.keys():
                        defectsAverages[defectCategory].append(categoryAverage)
                    else:
                        defectsAverages[defectCategory] = [categoryAverage]
        #End of adding averages to defectsAverages dict.

        #Handle elseValue (a category of 'other').
        #For now (8/10/2022), values under this category should be omited.
        #A proper logic will be developed in the future.
        if elseValue in defectsAverages.keys():
            del defectsAverages[elseValue]

        #Turn into categories:
        for category, averagesSum in defectsAverages.items():
            avgCeil = math.ceil(average(averagesSum))
            percent = toCategory(avgCeil, backwardsList, None)
            defectsCategories[category] = percent
        return defectsCategories

    def c__vitalforest_desc(self, vitalForestDict):
        """
        Takes the output of c__vitalforest() method:
        - vitalForestDict: dict with every defect type and its percent impact:
            {forest defect <str>: percent impact <str>, ...}
        Returns a concatenated <str> as follows:
        "defect type 1 - percent impact, defect type 2 - percent impact, ..."
        Sorted by percent value in descending order.
        """
        percentValues_sorted = [
            'אין',
            'זניח (3%-0%)',
            'מועט (10%-3%)',
            'בינוני (33%-10%)',
            'גבוה (66%-33%)',
            'גבוה מאוד (מעל 66%)'
        ]
        tupList = [(k,v) for k,v in vitalForestDict.items()]
        #Sort by the index of the percent impact (magnitude):
        tupList.sort(key=lambda x: percentValues_sorted.index(x[1]), reverse = True)

        #strList = ["defect type 1 - percent impact", "defect type 2 - percent impact"]
        strList = []
        for tup in tupList:
            defecttype = tup[0]
            proportion = tup[1]
            txt = "%s - %s" % (defecttype, proportion)
            strList.append(txt)
        
        if strList:
            concat = ", ".join(strList)
            return concat
        else:
            return None

    def c__invasivespecies(self):
        """
        For each invasive species that appears in points rel table,
        take the epicenter types, convert it to its index, ceil(avg()) them,
        and get the calculated epicenter type.
        returns a dict of {invasiveSpecies <str>: epicenterType <str>, ...}.
        """
        stepName = 'invasive species'
        #invasivespecies is the dict to be returned
        invasivespecies = {}
        #A list of valid values for invasive species:
        invasiveSpecies_codedValues = [
            None,
            "אין",
            "אזדרכת מצויה",
            "אילנתה בלוטית",
            "אמברוסיה מכונסת (ומינים נוספים)",
            "דודוניאה דביקה",
            "חמציץ נטוי",
            "חסת המים",
            "טטרקליניס מפריק",
            "טיונית החולות",
            "ינבוט המסקיטו יוליפלורה",
            "כסייה סטורטי",
            "לנטנה ססגונית",
            "פולובניית פורטון (פאולינה)",
            "פלפלון בכות",
            "פלפלון דמוי-אלה",
            "פרקנסוניה שיכנית",
            "צחר כחלחל",
            "שיטה ויקטוריה",
            "שיטה כחלחלה",
            "שיטה סליצינה (עלי ערבה)",
            "קיקיון מצוי",
            "אחר (פרט בהערות)",
        ]
        #indexes to ignore: None, "אין", "אחר"
        invasiveSpecies_indexesToOmit = [0, 1, len(invasiveSpecies_codedValues)-1]
        #A dict of {invasive species <str>: [epicenter type INDEX <int>, ...], ...}
        invasiveSpecies_indexLists = {}
        #An ascending sorted epicenter type list:
        epicenterType_codedValues = [
            None,
            "אין",
            "מוקד קטן",
            "מוקד בינוני",
            "מוקד גדול",
        ]
        #indexes to ignore: None, "אין"
        epicenterType_indexesToOmit = [0, 1]

        for point in self.points:
            for tup in point.invasivespecies:
                #tup - a tuple that represents a row in invasive forest related table.
                species = tup[0]
                epicenter = tup[1]
                #Two conditions for validity of values:
                validity_conditions = [
                    species in invasiveSpecies_codedValues,
                    epicenter in epicenterType_codedValues
                ]
                if False in validity_conditions:
                    #Values are not valid, add warning and skip.
                    txt = "Point %s: %s. Invalid value: (%s, %s)." % (point.FC.oidFieldName, point.id, species, epicenter)
                    self.notifier.add(stepName, 'warning', txt)
                    continue
                else:
                    #values are valid, convert to index, check if index
                    #should be omitted, if not - append to invasiveSpecies_indexLists.
                    species_index = invasiveSpecies_codedValues.index(species)
                    epicenter_index = epicenterType_codedValues.index(epicenter)
                    if (species_index in invasiveSpecies_indexesToOmit) or \
                        (epicenter_index in epicenterType_indexesToOmit):
                        continue
                    #Values are valid and wanted → append accordingly:
                    if species in invasiveSpecies_indexLists.keys():
                        #add to an existing "species" entry:
                        invasiveSpecies_indexLists[species].append(epicenter_index)
                    else:
                        #create a new "species" entry:
                        invasiveSpecies_indexLists[species] = [epicenter_index]
        #End of appending epicenter indexes to lists.

        #For every key (invasive species) in invasiveSpecies_indexLists,
        #ceil(average()) all the epicenter_indexes.
        for species, epicenter_indexes in invasiveSpecies_indexLists.items():
            epicenter_calculatedValue = math.ceil(average(epicenter_indexes))
            #turn calculated value to → epicenter type <str>
            epicenter = epicenterType_codedValues[epicenter_calculatedValue]
            invasivespecies[species] = epicenter
        
        return invasivespecies

    def c__invasivespecies_desc(self, invasivespeciesDict):
        """
        Takes the output of c__invasivespecies() method:
        - invasivespeciesDict: dict with every invasive species and its epicenterType:
            {invasiveSpecies <str>: epicenterType <str>, ...}
        Returns a concatenated <str> as follows:
        "invasive species 1 - epicenterType, invasive species 2 - epicenterType, ..."
        Sorted by epicenterType in descending order.
        """
        epicenterType_sorted = [
            None,
            "אין",
            "מוקד קטן",
            "מוקד בינוני",
            "מוקד גדול",
        ]
        defaultValue = epicenterType_sorted[1]
        tupList = [(k,v) for k,v in invasivespeciesDict.items()]
        #Sort by the index of the epicenterType (magnitude):
        tupList.sort(key=lambda x: epicenterType_sorted.index(x[1]), reverse = True)

        #strList = ["defect type 1 - percent impact", "defect type 2 - percent impact"]
        strList = []
        for tup in tupList:
            invasiveSpecies = tup[0]
            epicenterType = tup[1]
            if epicenterType not in epicenterType_sorted[:2]:
                # epicenterType is not None or 'אין'
                txt = "%s - %s" % (invasiveSpecies, epicenterType)
                strList.append(txt)
        
        if strList:
            concat = ", ".join(strList)
            return concat
        else:
            return defaultValue

    def c__naturalvalues(self):
        """
        Removes None and "אין" values,
        if other values exist → remove duplications → concatenate,
        else: return "אין"
        """
        rawValues = self.getRelatedValues('sp', 40063)
        domainValues = [
            None,
            "אין",
            "מינים בסכנת הכחדה",
            "ריכוז מינים מוגנים",
            "עצים או שיחי תפארת",
            "בית-גידול לח",
            "אתרי קינון",
            "מצוקים",
            "מאורות יונקים",
            "נוכחות צבאים",
            "ערכי טבע דוממים",
            "מטע או בוסתן עזוב",
            "אחר",
        ]
        defaultValue = domainValues[1] #'אין'
        elseValue = domainValues[12] #'אחר'
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        #make sure all values are valid:
        validValues = []
        for rawValue in rawValues:
            if rawValue in domainValues:
                validValues.append(rawValue)
        
        #convert to indexes:
        indexList = [domainValues.index(validValue) for validValue in validValues]
        #indexes to be removed:
        for indexToRemove in [0, 1]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        #logic:
        if indexList:
            #sort by frequency, remove duplications.
            indexList_sorted = freqSorted(indexList)
            #convert indexes back to values:
            valList = [domainValues[i] for i in indexList_sorted]
            if elseValue in valList:
                #1) move elseValue to end (if exists)
                valList = makeLast(valList, elseValue)
                #2) copy free text from the details field
                detailsList = self.getRelatedValues('sp', 40092)
                detailsList = removeDup(detailsList)
                for valueToRemove in ['',' ', None]:
                    while valueToRemove in detailsList:
                        detailsList.remove(valueToRemove)
                if detailsList:
                    # concatenate using "; "
                    resultsDict['details'] = '; '.join(detailsList)
            #remove default value if it exists along with other values
            if (defaultValue in valList) and (len(valList)>1):
                valList.remove(defaultValue)
            #concatenate:
            resultsDict['main'] = ",".join(valList)
            return resultsDict
        else:
            #list is empty, return defaultValue
            return resultsDict

    def c__roadsidesconditions(self):
        """
        Each row value is a concat with ",",
        remove unwanted values and duplications.
        If "תקין" coexists with other values - remove it.
        """
        #rawValues is a list of row values (string),
        #each string is a concatenation with ","s.
        rawValues = self.getRelatedValues('sp', 40064)
        valuesToOmit = ["", " "]
        defaultValue = "תקין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        #valid values are single values.
        validValues = []
        for rawValue in rawValues:
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = rawValue.split(',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        if validValues:
            #sort by frequency, remove duplications.
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                detailsList = self.getRelatedValues('sp', 40093)
                detailsList = removeDup(detailsList)
                for valueToRemove in ['',' ', None]:
                    while valueToRemove in detailsList:
                        detailsList.remove(valueToRemove)
                if detailsList:
                    # concatenate using "; "
                    resultsDict['details'] = '; '.join(detailsList)
            #remove default value if it exists along with other values
            if (defaultValue in validValues_sorted) and (len(validValues_sorted)>1):
                validValues_sorted.remove(defaultValue)
            #concatenate:
            resultsDict['main'] = ",".join(validValues_sorted)
            return resultsDict
        else:
            #list is empty, return defaultValue
            return resultsDict

    def c__limitedaccessibilitytype(self):
        """
        Each row value is a concat with ",",
        remove unwanted values and duplications.
        If "תקין" coexists with other values - remove it.
        """
        #rawValues is a list of row values (string),
        #each string is a concatenation with ","s.
        rawValues = self.getRelatedValues('sp', 40065)
        valuesToOmit = ["", " "]
        defaultValue = "אין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        #valid values are single values.
        validValues = []
        for rawValue in rawValues:
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = rawValue.split(',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        if validValues:
            #sort by frequency, remove duplications.
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                detailsList = self.getRelatedValues('sp', 40094)
                detailsList = removeDup(detailsList)
                for valueToRemove in ['',' ', None]:
                    while valueToRemove in detailsList:
                        detailsList.remove(valueToRemove)
                if detailsList:
                    # concatenate using "; "
                    resultsDict['details'] = '; '.join(detailsList)
            #remove default value if it exists along with other values
            if (defaultValue in validValues_sorted) and (len(validValues_sorted)>1):
                validValues_sorted.remove(defaultValue)
            #concatenate:
            resultsDict['main'] = ",".join(validValues_sorted)
            return resultsDict
        else:
            #list is empty, return defaultValue
            return resultsDict

    def c__foresthazards(self):
        """
        Each row value is a concat with ",",
        remove unwanted values and duplications.
        If "תקין" coexists with other values - remove it.
        """
        #rawValues is a list of row values (string),
        #each string is a concatenation with ","s.
        rawValues = self.getRelatedValues('sp', 40066)
        valuesToOmit = ["", " ", None]
        defaultValue = "אין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        #valid values are single values.
        validValues = []
        for rawValue in rawValues:
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = rawValue.split(',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        if validValues:
            #sort by frequency, remove duplications.
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                detailsList = self.getRelatedValues('sp', 40095)
                detailsList = removeDup(detailsList)
                for valueToRemove in ['',' ', None]:
                    while valueToRemove in detailsList:
                        detailsList.remove(valueToRemove)
                if detailsList:
                    # concatenate using "; "
                    resultsDict['details'] = '; '.join(detailsList)
            #remove default value if it exists along with other values
            if (defaultValue in validValues_sorted) and (len(validValues_sorted)>1):
                validValues_sorted.remove(defaultValue)
            #concatenate:
            resultsDict['main'] = ",".join(validValues_sorted)
            return resultsDict
        else:
            #list is empty, return defaultValue
            return resultsDict

    def c__forestdegeneration(self):
        """
        Calculate stand's vital cover average, and return its category <str>.
        """
        domainValues = {
            #value <str>: (ceil of avg <int>, max <int>),
            "אין": (0, 0),
            "זניח (3%-0%)": (2, 3),
            "מועט (10%-3%)": (7, 10),
            "בינוני (33%-10%)": (22, 33),
            "גבוה (66%-33%)": (50, 66),
            "גבוה מאוד (מעל 66%)": (88, 100),
        }
        defaultValue = "אין"
        backwardsList = [(v[1],k) for k,v in domainValues.items()]

        vitalcover_category_val = [point.vitalcover for point in self.points]
        #filter:
        unwantedValues = [None]
        for unwantedValue in unwantedValues:
            while unwantedValue in vitalcover_category_val:
                vitalcover_category_val.remove(unwantedValue)
        #convert each category val to its ceil of avg:
        vitalcover_avgs_val = [domainValues[category][0] for category in vitalcover_category_val]
        if vitalcover_avgs_val:
            avg = math.ceil(average(vitalcover_avgs_val))
            category = toCategory(avg, backwardsList)
            return category
        else:
            #list is empty. return default value.
            return defaultValue

    def c__totalcoverage(self):
        """
        Checks if field 'totalCoverage' has value.
        If it has - return it.
        If it does not - take values of all 3 cover layers and solve a matrix.
        """
        stepName = 'totalcoverage'
        rawValue = self.getSelfValue(50088)
        forestLayerCovers_fieldCodes = [50047,50051,50055]
        unwantedValues = [None, '']
        if rawValue not in unwantedValues:
            return rawValue
        else:
            forestLayerCovers = self.getSelfValue(forestLayerCovers_fieldCodes)
            #Replace ('' or None) with 'אין' for the calculation:
            valuesToReplace = ['', None]
            replaceWith = 'אין'
            for valueToReplace in valuesToReplace:
                if valueToReplace in forestLayerCovers:
                    forestLayerCovers = replaceInList(forestLayerCovers, valueToReplace, replaceWith)
            
            matrix_solution = totalCoverageCoordinator.solve(forestLayerCovers)

            if matrix_solution['errorMessage']:
                #That means something went wrong and a warning should be raised.
                txt = matrix_solution['errorMessage']
                self.notifier.add(stepName, 'warning', txt)
            
            return matrix_solution['value']
      
    def c__date(self):
        """
        Returns the max date of the point's date.
        If list of dates is empty - return None.
        """
        dates = self.getRelatedValues('sp', 40004)
        while None in dates:
            dates.remove(None)
        if dates:
            return max(dates)
        else:
            return None

    def c__dunam(self):
        """
        Returns the stand's area in dunam, using geodesic method.
        """
        shape = self.getSelfValue(50001)
        area_m3 = shape.getArea("GEODESIC", "SquareMeters")
        area_dunam = area_m3/1000
        return area_dunam

class SekerPoint(FcRow):
    def __init__(self, parentFcRow, row, sekerpointsFC):
        FcRow.__init__(self, row, sekerpointsFC)
        self.parent = parentFcRow
        self.notifier = self.parent.notifier

        #self.covtype = list of tuples: [(treecode <str>, proportion <str>), ...]
        self.covtype = self.getRelatedValues('pt3', [43005, 43006])
        #self.planttype = dictionary of {plant type <str>: cover percent <int>, ...}
        self.planttype = self.buildPlantTypeDict()
        #self.vitalforest = list of tuples: [(forest defect <str>, percent inpact <str>), ...]
        self.vitalforest = self.getRelatedValues('pt4', [44002, 44003])
        #self.vitalcover = sekerpoint's vital cover from Totalvitalcover or related table.
        self.vitalcover = self.calculatevitalcover()
        #self.invasivespecies = list of tuples: [(invasive species <str>, epicenter type <str>), ...]
        self.invasivespecies = self.getRelatedValues('pt1', [41002, 41003])
        #self.generaldensity = seker-point's general density <str> (domained).
        self.generaldensity = self.getSelfValue(40020)

        #Layer objects: (outputs of classification tool).
        self.layers = {
            'tmira': ForestLayer(self, 4),
            'high': ForestLayer(self, 3),
            'mid': ForestLayer(self, 2),
            'sub': SubForestLayer(self)
        }

    def __repr__(self):
        return "SekerPoint object, id = %s" % self.id

    def buildPlantTypeDict(self):
        """
        Return Plant Type Cover distribution based on values in 
        each point's PlantTypeCoverDistribut related table.
        Steps:
        1) populate with existing values.
        2) supllement to "ללא כיסוי" if necessary until sum == 100%
        Returns: a dictionary { plant type <str>: cover percent <int>}
        """
        stepName = 'build plant type dict'
        plantTypeDict = {
            "צומח_גדות_נחלים": 0,
            "עצים": 0,
            "שיחים": 0,
            "בני_שיח": 0,
            "עשבוני": 0,
            "ללא_כיסוי": 0,
            "מינים_פולשים": 0
        }
        #rawValues is a list of tuples: [(plant type <str>, percent <str>), ..]
        rawValues = self.getRelatedValues('pt2',[42002, 42003])
        elseKey = "ללא_כיסוי"

        for tup in rawValues:
            plantType = tup[0]
            percent = tup[1]
            #Handle values of percent.
            # *see classification script SubForestLayer.subForestCover()
            if percent in [None, "", "0%"]:
                percent = 0
            else:
                percent = int(percent.replace("%",""))
            
            #Handle values of plant type that are not in plantTypeDict.keys():
            #→warn and skip to next row.
            if (plantType not in plantTypeDict.keys()) or (plantType is None):
                txt = "Plant type of subforest is not valid. Point %s: %s." % (self.FC.oidFieldName, self.id)
                self.notifier.add(stepName, 'warning', txt)
                continue

            #assign values in a cumulative way:
            plantTypeDict[plantType] += percent
        
        #supllement to "ללא כיסוי" if necessary until sum == 100%
        percentSum = sum(plantTypeDict.values())
        sumIsAMultipleOfTen = percentSum%10 == 0
        if not sumIsAMultipleOfTen:
            #a rare case → add ERROR.
            errorMessage = "Sum of subforest plant type is not a multiple of 10. SekerPoint %s: %s." % (self.FC.oidFieldName, self.id)
            arcpy.AddWarning(errorMessage)
            return None
        elif percentSum < 100:
            #warn:
            warningMessage = "Sum of subforest plant type is less than 100. SekerPoint %s: %s." % (self.FC.oidFieldName, self.id)
            arcpy.AddWarning(warningMessage)
            delta = 100 - percentSum
            #complete to 100:
            plantTypeDict[elseKey] += delta

        return plantTypeDict

    def calculatevitalcover(self):
        """
        Calculates sekerpoint's vital cover, according to the requirements
        of c__forestdegeneration.
        The source of vital cover is different, and depends on whether
        sekerpoints field TotalVitalCover has a value or isNone:
            -If TotalVitalCover has value other than None: return this value.
            -If TotalVitalCover is None:
                1)return sekerpoint's MAX vital forest value (from related table).
                2)write this value (MAX) into sekerpoints' TotalVitalCover field.
        Returns category <str> (that belongs to the domain: cvd_PercentImpact).
        """
        #19/3/23
        totalVitalCover_fieldCode = 40118
        rawValue = self.getSelfValue(totalVitalCover_fieldCode)
        if rawValue is not None:
            return rawValue
        else:
            percentValues_sorted = [
                'אין',
                'זניח (3%-0%)',
                'מועט (10%-3%)',
                'בינוני (33%-10%)',
                'גבוה (66%-33%)',
                'גבוה מאוד (מעל 66%)'
            ]
            defaultValue = "אין"
            values = self.getRelatedValues('pt4', 44003)
            while None in values: values.remove(None)
            values.sort(key= lambda x: percentValues_sorted.index(x), reverse = True)
            if values:
                calculatedValue = values[0]
            else:
                calculatedValue = defaultValue
            #write calculatedValue into sekerpoints' TotalVitalCover field:
            self.writeSelf(totalVitalCover_fieldCode, calculatedValue)
            return calculatedValue
        """
        #Check if sekerpoints FC has this field:
        hasOwnField = fieldsDict[40118].name.lower() in \
        [f.name.lower() for f in org.sekerpoints.desc.fields]
        if hasOwnField:
            return self.getSelfValue(40118)
        else:
            percentValues_sorted = [
                None,
                'אין',
                'זניח (3%-0%)',
                'מועט (10%-3%)',
                'בינוני (33%-10%)',
                'גבוה (66%-33%)',
                'גבוה מאוד (מעל 66%)'
            ]
            values = self.getRelatedValues('pt4', 44003)
            values.sort(key= lambda x: percentValues_sorted.index(x), reverse = True)
            return values[0]
        """

class Layer:
    """
    An empty layer object.
    """
    def __init__(self, parent):
        self.parent = parent
        self.isValid = False
        self.isForestLayer = False
        self.isPrimary = False
        self.isSecondary = False
        self.layerDesc = None
        self.layerNum = None
        self.layerShortText = None
        self.layerLongText = None
        self.vegForm = None
        self.vegForm_translated = None
        self.vegForms = []
        self.layerCover = None
        self.layerCover_num = None
        self.layerCover_avg = None
        self.speciesCodes = []
        self.speciesNames = []
    def __repr__(self):
        return "Empty layer object"

class ForestLayer(Layer):
    """
    A layer that is built based on raw untouched fields of sekerpoints,
    and holds their attributes:
    - layer
    - cover
    - veg form
    - species
    Queries the sekerpoint's attributes a desired layer.
    Input parameters:
    - sekerpoint - a SekerPoint object (parent).
    - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
    """
    def __init__(self, parent, layerNum):
        Layer.__init__(self, parent)
        self.isForestLayer = True
        self.layerNum = layerNum
        if self.layerNum not in [2,3,4]:
            raise Exception('Invalid layerNum inserted: %s' % self.layerNum)
        self.layerShortText = layerToShortText[self.layerNum]
        self.layerLongText = layerToLongText[self.layerNum]
        self.layerLongText_m = layerToLongText_m[self.layerNum]
        #based on the fields primary/secondary_forestLayer,
        #decide whether the layer is primary, secondary, or not either.
        self.isPrimary = self.layerLongText == self.parent.getSelfValue(40103)
        self.isSecondary = self.layerLongText == self.parent.getSelfValue(40107)
        stepName = '%s forest layer creation' % self.layerShortText

        #Import values from sekerpoint
        #fieldsList = [vegForm, layerCover, species]
        fieldLists = {
            4: [40024, 40025, 40026],
            3: [40034, 40035, 40036],
            2: [40044, 40045, 40046],
        }
        fieldsList = fieldLists[self.layerNum]
        #query
        rawValues = self.parent.getSelfValue(fieldsList)

        #3 raw values: [vegForm, layerCover, species]
        self.vegForm = rawValues[0]
        self.vegForm_translated = translate(self.vegForm, subForestVegForm_translation)
        self.layerCover = rawValues[1]
        speciesCodes_raw = rawValues[2]

        #validation and elaboration of values:
        #A counter of valid tests passed:
        validationConditionsMet = 0
        #1) Validation of layercover:
        try:
            layerCover_tup = layerCover_table1[self.layerCover]
            self.layerCover_num = layerCover_tup[0]
            self.layerCover_avg = layerCover_tup[1]
        except KeyError as e:
            #self.layerCover is not a valid value.
            key = e.args[0]
            if key not in ['', None]:
                #self.layerCover is not one of .keys() nor is "" / None:
                layerCover_validValues = list(layerCover_table1.keys())
                layerCover_validValues += [None, '']
                txt = 'Point %s: %s. Layer cover value (%s) not one of the following: %s.'\
                    % (self.parent.FC.oidFieldName, self.parent.id, key, layerCover_validValues)
                self.parent.notifier.add(stepName, 'warning', txt)
        else:
            validationConditionsMet += 1
        
        #2) Validation of species:
        if hasattr(speciesCodes_raw, 'split') and speciesCodes_raw != '':
            #speciesCodes_raw can be splitted.
            #split and iterate:
            speciesCodes_split = speciesCodes_raw.split(',')
            #remove unwanted ' ' spaces from all splitValues:
            speciesCodes_split = [splitVal.replace(' ', '') for splitVal in speciesCodes_split]
            for splitVal in speciesCodes_split:
                try:
                    #try to match every code to its complement species name:
                    speciesCode = int(splitVal)
                    speciesName = speciesDict[speciesCode]
                except ValueError:
                    #splitVal is not intable.
                    continue
                except KeyError as e:
                    #Species code: not found in speciesDict.
                    #Notifty and move on to next splitVal.
                    key = e.args[0]
                    txt = 'Point %s: %s. Species code value (%s) is not found in: "%s".'\
                        % (self.parent.FC.oidFieldName, self.parent.id, key, speciesDict['__jsonFileName__'])
                    self.parent.notifier.add(stepName, 'warning', txt)
                    continue
                else:
                    #Conditions are met:
                    #-splitVal is intable.
                    #-species code is in species dict.
                    self.speciesCodes.append(speciesCode)
                    self.speciesNames.append(speciesName)
        #End of validating and elaborating species. Check what came out:
        if self.speciesCodes:
            #e.g., len > 0
            validationConditionsMet += 1

        #3) Validation of vegform: (similar to species)
        if hasattr(self.vegForm, 'split') and self.vegForm != '':
            vegForm_possibleValues = [
                #@validate values with Achiad.
                "מחטני",
                "חורש",
                "רחבי-עלים",
                "בוסתנים_ומטעים",
                "שיטים",
                "שיטים_פולשני",
                "איקליפטוס",
                "יער_גדות_נחלים",
                "אשלים",
            ]
            #self.vegForm can be splitted.
            #split and iterate:
            vegForm_split = self.vegForm.split(',')
            #remove unwanted ' ' spaces from all splitValues:
            vegForm_split = [splitVal.replace(' ', '') for splitVal in vegForm_split]
            for splitVal in vegForm_split:
                try:
                    if splitVal not in vegForm_possibleValues:
                        raise KeyError(splitVal)
                except KeyError as e:
                    key = e.args[0]
                    txt = 'Point %s: %s. Veg form value (%s) is not one of the following: %s.'\
                    % (self.parent.FC.oidFieldName, self.parent.id, key, vegForm_possibleValues)
                    self.parent.notifier.add(stepName, 'warning', txt)
                else:
                    if splitVal not in self.vegForms:
                        self.vegForms.append(splitVal)
        if self.vegForms:
            validationConditionsMet += 1

        #end of validation, valid only if passed 3 tests:
        if validationConditionsMet == 3:
            self.isValid = True

        return

    def asText(self):
        return "Layer object. Desc: %s." % self.layerDesc

    def __repr__(self):
        #return self.asText()
        validity = {True:'valid',False:'invalid'}[self.isValid]
        return "Layer object: %s [%s]." % (self.layerShortText, validity)

class SubForestLayer(Layer):
    """
    Except layer num, short and long text, this layer
    does not have any stand-alone values (cover and veg form).
    Instead, this sub-forest layer will be given the remaining 
    values (cover and veg form) only if it had been classified
    as a primary or secondary layer for the point (during the
    process of classification.py). In that case, the enhance
    method handles cover and veg form attributes.
    """
    def __init__(self, parent, layerNum = 1):
        Layer.__init__(self, parent)
        self.layerNum = layerNum
        self.layerShortText = layerToShortText[self.layerNum]
        self.layerLongText = layerToLongText[self.layerNum]
        self.layerLongText_m = layerToLongText_m[self.layerNum]
        #based on the fields primary/secondary_forestLayer,
        #decide whether the layer is primary, secondary, or not either.
        self.isPrimary = self.layerLongText == self.parent.getSelfValue(40103)
        self.isSecondary = self.layerLongText == self.parent.getSelfValue(40107)
        stepName = 'subforest layer creation'

        #Validation parameter:
        validationConditionsMet = 0

        #Until now, the basic part of creating a sub-forest layer
        #is done.

        #If the layer is primary or secondary, add information:
        if self.isPrimary or self.isSecondary:
            #create fieldCodes list for primary / secondary:
            #fieldCodes = [vegForm, layerCover]
            if self.isPrimary:
                fieldCodes = [40104, 40105]
            else:
                fieldCodes = [40108, 40109]
            values = self.parent.getSelfValue(fieldCodes)
            self.vegForm = values[0]
            self.vegForm_translated = translate(self.vegForm, subForestVegForm_translation)
            self.layerCover = values[1]

            #1) Validation of layerCover:
            try:
                layerCover_tup = layerCover_table1[self.layerCover]
                self.layerCover_num = layerCover_tup[0]
                self.layerCover_avg = layerCover_tup[1]
            except KeyError as e:
                #self.layerCover is not a valid value.
                key = e.args[0]
                if key not in ['', None]:
                    #self.layerCover is not one of .keys() nor is "" / None:
                    layerCover_validValues = list(layerCover_table1.keys())
                    layerCover_validValues += [None, '']
                    txt = 'Point %s: %s. Layer cover value (%s) not one of the following: %s.'\
                        % (self.parent.FC.oidFieldName, self.parent.id, key, layerCover_validValues)
                    self.parent.notifier.add(stepName, 'warning', txt)
            else:
                validationConditionsMet += 1
            
            #2) Validation of vegForm
            if self.vegForm not in ['',None]:
                self.vegForms = [self.vegForm]
                validationConditionsMet += 1

        if validationConditionsMet == 2:
            self.isValid = True

    def __repr__(self):
        #return self.asText()
        validity = {True:'valid',False:'invalid'}[self.isValid]
        return "Layer object: %s [%s]." % (self.layerShortText, validity)

class LayerResult(Layer):
    """
    A rerult object to help hold information with the method
    'c__logiclayers()' in standPolygon class.
    """
    def __init__(self):
        Layer.__init__(self, None)
        self.assigned = False

    def assign(self, layerNum, cover):
        self.assigned = True

        self.layerNum = layerNum
        if self.layerNum in [4,3,2]:
            self.isForestLayer = True
        self.layerShortText = layerToShortText[layerNum]
        self.layerLongText = layerToLongText[layerNum]
        self.layerLongText_m = layerToLongText_m[layerNum]
        
        self.layerCover = cover
        self.layerCover_num = layerCover_table1[cover][0]
        self.layerCover_avg = layerCover_table1[cover][1]
    
    def setVegForm(self, vegForm):
        self.vegForm = vegForm
        self.vegForm_translated = translate(vegForm, subForestVegForm_translation)
        self.vegForms = [vegForm]

    def createDesc(self):
        descTxt = "%s %s %s" % (
                    self.vegForm,
                    self.layerLongText_m,
                    self.layerCover,
                )
        self.layerDesc = descTxt
    
    def finalize(self):
        #1) validate:
        if None not in [self.vegForm, self.layerLongText, self.layerCover]:
            #That means that both methods (setVegForm & assign) performed.
            self.isValid = True
        #2) create description:
        if self.isValid:
            self.createDesc()

    def getValuesToWrite(self):
        #Returns a list of values to be used when writing
        #the results into stand polygon fields.
        #Values are in the following order:
        #[forest layer, veg form transtaled, layer cover, layer desc]
        #exactly like ther appear in fieldCodes in
        #calculateAndWrite() method.
        return [
                self.layerLongText,
                self.vegForm_translated,
                self.layerCover,
                self.layerDesc
            ]
        """
        #deprecated: invalid layers returned 'אין' instead of Null in all 4 fields.
        if self.isValid:
            return [
                self.layerLongText,
                self.vegForm_translated,
                self.layerCover,
                self.layerDesc
            ]
        else:
            #This layer is not valid, write 'אין' in all 4 fields:
            return ['אין']*4
        """

    def __repr__(self):
        #return self.asText()
        validity = {True:'valid',False:'invalid'}[self.isValid]
        return "LayerResult object: %s [%s]." % (self.layerDesc, validity)

class CovtypeResult:
    #A reciprocal object for SpeciesCompositionResult (classification_may2022_v2.py).
    #can be used as an empty placeholder
    def __init__(self, standPolygon = None, speciesComp_matrixObj = None, vegForms_matrixObj = None):
        self.standPolygon = standPolygon
        self.speciesComp_matrixObj = speciesComp_matrixObj
        self.vegForms_matrixObj = vegForms_matrixObj
        self.mode = None
        self.assigned = False
        self.converted = False
        self.singleNode = Node()
        self.doubleNode = []
        #Two values to be used as output:
        self.str = ""
        self.code = None
        
    def assignStudy(self):
        self.mode = "study"
        self.assigned = True
        self.str = "מחקר"
        self.code = 9970

    def assignNode(self, node):
        self.singleNode = node
        self.mode = "single"
        self.assigned = True
        self.str = self.singleNode.name
        self.str = translate(self.str, subForestVegForm_translation)
        self.code = int(self.singleNode.codedValue)
        self.convert()

    def convert(self):
        #This method CHECKS if a conversion (to altered node and result)
        #and converts it.
        #Works only for self.mode == "single".
        sourceNode = self.singleNode
        if (self.mode == "single") and (sourceNode.hasAlternative()):
            alternativeNode_reflection = findNode(root, sourceNode.altCode)
            #findNode might not find any node, and return an empty node.
            #in case this happens - notify.
            if alternativeNode_reflection.isEmpty():
                txt = 'Could not find alternative node. Origin code: %s, Destination code: %s.' \
                % (sourceNode.codedValue, sourceNode.altCode)
                stepName = 'covtype'
                self.standPolygon.notifier.add(stepName, 'warning', txt)
            alt_name = alternativeNode_reflection.name
            alt_codedValue = alternativeNode_reflection.codedValue
            #set the singleNode to a NEW one: (not a reflection)
            self.singleNode = Node(alt_name, alt_codedValue)
            self.converted = True
            self.str = self.singleNode.name
            self.str = translate(self.str, subForestVegForm_translation)
            self.code = self.singleNode.codedValue
        return
    """
    def convert_old(self):
        #This method CHECKS if a conversion (to altered node and result)
        #and converts it.
        #Works only for self.mode == "single".
        source_codedValue = self.singleNode.codedValue
        if (self.mode == "single") and (int(source_codedValue) in speciesConversions.keys()):
            conv_dict = speciesConversions[int(source_codedValue)]
            alt_name = conv_dict['alt_name']
            alt_codedValue = conv_dict['alt_codedValue']
            #set the singleNode to a new one:
            self.singleNode = Node(alt_name, alt_codedValue)
            self.converted = True
            self.str = self.singleNode.name
            self.code = int(self.singleNode.codedValue)
            #self.sekerPoint.warnings.append("Species composition converted from %s to %s." % (source_codedValue, alt_codedValue))
        return
    """
    def assignNodes(self, nodesList):
        self.doubleNode = nodesList
        self.mode = "double"
        self.assigned = True
        nodeNames = [n.name for n in self.doubleNode]
        matrixResult = self.speciesComp_matrixObj.solve(nodeNames)
        self.str = matrixResult
        self.str = translate(self.str, subForestVegForm_translation)
        #find the node of "מעורב ___ " by searching its name:
        foundNode = findNodeByName(root, self.str)
        if foundNode.isEmpty():
            self.code = None
        else:
            self.code = foundNode.codedValue

    def assignLayer(self, layer):
        #deprecated.
        #assign value based on a layer object.
        self.mode = "layer"
        self.assigned = True
        self.str = layer.vegForm
        self.str = translate(self.str, subForestVegForm_translation)
    def assignLayers(self, layersList):
        #assign value based on two layer objects.
        self.mode = "layers"
        self.code = None
        self.assigned = True
        layersVegForms = [l.vegForm for l in layersList]
        matrixResult = self.vegForms_matrixObj.solve(layersVegForms)
        self.str = matrixResult
        self.str = translate(self.str, subForestVegForm_translation)
    def assignBroadleaf(self, covtypeString):
        #used when a SINGLE NODE was assigned and found to be 'מעורב רחבי-עלים'.
        #hence, this method resets the actions of self.assignNode.
        self.singleNode = Node()
        self.mode = "broadLeaf"
        self.assigned = True
        #find the node by its translated name:
        self.str = translate(covtypeString, subForestVegForm_translation)
        foundNode = findNodeByName(root, self.str)
        if foundNode.isEmpty():
            self.code = None
        else:
            self.code = foundNode.codedValue

    def assignSubForest(self, covtypeString):
        self.mode = "subForest"
        self.assigned = True
        #find the node by its translated name:
        self.str = translate(covtypeString, subForestVegForm_translation)
        foundNode = findNodeByName(root, self.str)
        if foundNode.isEmpty():
            self.code = None
        else:
            self.code = foundNode.codedValue


        

    def __repr__(self):
        return self.asText()
    def asText(self):
        return "name: %s. code: %s." % (self.str, self.code)

class SmallField:
    """
    An object with easy access to field details.
    """
    def __init__(self, code, name, alias, type, domain, checkIfExists, sequence, toAdd, length = None):
        self.code = code
        self.name = name
        self.alias = alias
        self.type = type
        self.domain = domain
        self.length = length
        #toAdd: Formerly 1/<blank> (for True/False). Now 'keepValues'/'blank'/'' (<string>).
        self.toAdd = toAdd
        #Turn all None sequence to (-infinity):
        if sequence is not None:
            self.sequence = sequence
        else:
            self.sequence = math.inf
        if checkIfExists == 1:
            self.checkIfExists = True
        else:
            self.checkIfExists = False

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

class MatrixCoordinator:
    #An object that initializes and deals with matrices.
    def __init__(self, xlPath):
        #ATTENTION!
        #in order for this matrix to be consistent with the exact same
        #strings provided in the excel table, always use field's ALIAS name.

        #Notify in UI about process start:
        message = 'Creating matrix object: %s' % os.path.basename(xlPath)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)

        overwrite_original = arcpy.env.overwriteOutput
        arcpy.env.overwriteOutput = True
        #tblPath = os.path.join(arcpy.env.scratchGDB,"matrix")
        tblPath = os.path.join(arcpy.env.workspace,"matrix")
        arcpy.ExcelToTable_conversion(xlPath, tblPath)

        #Notify in UI about table dimensions:
        #minus 2 because of added objectid and the values under "X" cell.
        Ncol = len(arcpy.Describe(tblPath).fields) - 2
        Nrow = getFeatureCount(tblPath)
        message = 'Creating matrix object: %s. Table dimensions: %sx%s' % (os.path.basename(xlPath), Ncol, Nrow)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)
        
        #This is the dict to be constructed in this __init__() method
        #and be availabe for use later:
        #{("column", "row"): "value"}
        self.coordinationDict = {}
        self.basename = os.path.basename(xlPath)
        
        
        allFields = arcpy.ListFields(tblPath)
        oidFieldName = getOidFieldName(tblPath).upper()
        #Check if 'X' field exists.
        if 'X' not in [f.name.upper() for f in allFields]:
            arcpy.AddError('Excel table has no header called "X".')
        
        #Select fields that are not objectid nor 'X':
        fields = []
        for field in allFields:
            name = field.name.upper()
            if name not in [oidFieldName, 'X']:
                fields.append(field)
        
        #Collect details for validation afterwards:
        columns_N = len(fields)
        columns_headings = [field.aliasName for field in fields]
        #rows will be counted in the sc iteration:
        rows_N = 0
        rows_headings = []

        #Construct self.coordinationDict using cursor:
        sc = arcpy.SearchCursor(tblPath)
        for r in sc:
            #Use .lower() method for uniformity of the text "other".
            secondary = r.getValue('X').lower()
            rows_N += 1
            rows_headings.append(secondary)
            for field in fields:
                #Use alias to keep exact same string.
                primary = field.aliasName.lower()
                value = r.getValue(field.name)
                self.coordinationDict[(primary, secondary)] = value
        del sc

        #self.inputOptions~ is a list of all possible columns or rows:
        self.inputOptions = set()
        for inpt in rows_headings:
            self.inputOptions.add(inpt)
        for inpt in columns_headings:
            self.inputOptions.add(inpt)

        #Validate table after constructing:
        validation = {
            "rows equal columns": {
                "condition": columns_N == rows_N,
                "warning message": "%s מספר שורות לא שווה למספר העמודות" % self.basename
            },
            "headings are identical": {
                "condition": sorted(rows_headings) == sorted(columns_headings),
                "warning message": "%s טקסט כותרות עמודות לא זהה לכותרות שורות." % self.basename
            }
        }

        #Use warning messages:
        for validationCriteria in validation.keys():
            criteriaDict = validation[validationCriteria]
            if criteriaDict["condition"] == False:
                arcpy.AddWarning(criteriaDict["warning message"])

        arcpy.env.overwriteOutput = overwrite_original
        arcpy.Delete_management(tblPath)
        arcpy.ResetProgressor()

    def solve(self, raw_values):
        """
        Returns elaborated vegForm and handles values that fall
        within 'other' category.
        - raw_values: [vegForm1 <str>, vegForm2 <str>].
        #NOTICE! this method's argument is slightly different than
        the one belongs to its counterpart in "classification may22".
        """
        #values: a list of validated inputs that can be used for the
        #2x2 matrix.
        values = []
        #If the inputs are equal and both fall in 'other':
        #then return the input and don't handle them both as 'other'.
        if len(raw_values) == 0:
            return None
        elif len(raw_values) == 1:
            #All values are the same.
            return raw_values[0]
        elif len(raw_values) == 2:
            for raw_value in raw_values:
                if raw_value in self.inputOptions:
                    values.append(raw_value)
                else:
                    #If it's not a known input value, turn it into 'other'.
                    values.append('other')
            values = tuple(values)
            return self.coordinationDict[values]
        elif len(raw_values) > 2:
            return '!number of inputs to matrix "%s" > 2' % self.basename

class Matrix3DCoordinator:
    #An object that initializes and deals with 3D matrices.
    def __init__(self, xlPath):
        #Notify in UI about process start:
        message = 'Creating 3D matrix object: %s' % os.path.basename(xlPath)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)

        overwrite_original = arcpy.env.overwriteOutput
        arcpy.env.overwriteOutput = True
        #tblPath = os.path.join(arcpy.env.scratchGDB,"matrix")
        tblPath = os.path.join(arcpy.env.workspace,"matrix")
        arcpy.ExcelToTable_conversion(xlPath, tblPath)

        #Import possible values for each dimension and output values
        #from the dimension's field domain.
        self.dimensions = [
            {
                'name': 'beitGidul',
                'source': 'tool input',
                'domain': 'tool input',
                'domainValues': beitgidulList
            },
            {
                'name': 'ageGroup',
                'source': fieldsDict[40022].name,
                'domain': fieldsDict[40022].domain,
                'domainValues': listCodedValues(org.sekerpoints.workspace, fieldsDict[40022].domain)
            },
            {
                'name': 'generalDensity',
                'source': fieldsDict[50042].name,
                'domain': fieldsDict[50042].domain,
                'domainValues': listCodedValues(org.sekerpoints.workspace, fieldsDict[50042].domain)
            },
            {
                'name': 'relativeDensity',
                'source': fieldsDict[50044].name,
                'domain': fieldsDict[50044].domain,
                'domainValues': listCodedValues(org.sekerpoints.workspace, fieldsDict[50044].domain)
            },
        ]

        #Notify in UI about table dimensions x, y, z:
        #X- number of different values under "COL_A".
        #Y- number of different values under "COL_B".
        #Z- number of different values under FIRST ROW.
        x_set = set()
        y_set = set()
        z_set = set()
        sc = arcpy.da.SearchCursor(tblPath, '*')
        firstRow = sc.next()[3:] #w/o objectid and headers of x and y.
        for z_value in firstRow:
            z_set.add(z_value)
        #now go through all other rows:
        for r in sc:
            x = r[1]
            y = r[2]
            x_set.add(x)
            y_set.add(y)
        del sc
        

        self.tableDimensions = [len(dim) for dim in [x_set, y_set, z_set]]
        self.keysByDimension = [list(s) for s in [x_set, y_set, z_set]]
        
        message = 'Creating 3D matrix object: %s. Table dimensions: %s' % (os.path.basename(xlPath), "x".join([str(d) for d in self.tableDimensions]))
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)
        
        #Notify for every dimension value that is not in domainValues:
        #לעבור על כל סט איקס וואי זד ולהכניס וורנינג במידה והוא לא מופיע באופציות פוסיביליטיז
        for i, dimDict in enumerate(self.dimensions[:3]):
            domainValues = dimDict['domainValues']
            tableValues = self.keysByDimension[i]
            for tValue in tableValues:
                if tValue not in domainValues:
                    txt = '\t-Table value "%s" does not appear in domain "%s" of field "%s"' % (tValue, dimDict['domain'], dimDict['source'])
                    arcpy.AddWarning(txt)

        #This is the dict to be constructed in this __init__() method
        #and be availabe for use later:
        #{("x", "y", "z"): "value"}
        self.coordinationDict = {}
        self.basename = os.path.basename(xlPath)

        #Construct self.coordinationDict using cursor:
        sc = arcpy.da.SearchCursor(tblPath, '*')
        firstRow = sc.next()
        rowLen = len(firstRow)
        indicesOfValue = list(range(3,len(firstRow)))
        for r in sc:
            x = r[1]
            y = r[2]
            #now iterate through relevant columns:
            for colIndex in indicesOfValue:
                z = firstRow[colIndex]
                value = r[colIndex]
                self.coordinationDict[(x, y, z)] = value
                #Notify in case value is not in its domainValues:
                if value not in self.dimensions[3]['domainValues']:
                    dimDict = self.dimensions[3]
                    txt = '\t-Table value "%s" does not appear in domain "%s" of field "%s"' % (value, dimDict['domain'], dimDict['source'])
                    arcpy.AddWarning(txt)
        del sc
        
        arcpy.env.overwriteOutput = overwrite_original
        arcpy.Delete_management(tblPath)
        arcpy.ResetProgressor()

    def solve(self, raw_values):
        outputDict = {
            'value': None,
            'errorMessage': None
        }
        #raw_values: a tuple (len=3) of validated inputs.
        tup = tuple(raw_values)

        #default value is error + table name + values
        #defaultValue = "matrix error %s: %s" % (self.basename, str(tup))
        defaultValue = "שגיאה"

        #VALIDATION:
        #1) length of tup must be 3:
        if len(tup) == 3:
            #2) check if all 3 values are among the options:
            # a list of 3 booleans, one for each dimension.
            conditions = [v in self.keysByDimension[i] for i,v in enumerate(tup)]
            falseIndices = [i for i,v in enumerate(conditions) if v is False]
            if falseIndices:
                dimensionNameAndValue = [f"{self.dimensions[i]['name']}: {tup[i]}" for i in falseIndices]
                dimensionNameAndValue_str = ', '.join(dimensionNameAndValue)
                outputDict = {
                    'value': defaultValue,
                    'errorMessage': 'The following values are not among the options: %s. Check table "%s"' % (dimensionNameAndValue_str, self.basename)
                }
                return outputDict
            else:
                #All of the values are valid, proceed.
                outputVal = self.coordinationDict[tup]
                outputDict['value'] = outputVal
                #If outputVal does not appear in the output field's domain:
                outDimDict = self.dimensions[3]
                if outputVal not in outDimDict['domainValues']:
                    txt = 'Value "%s" does not appear in domain "%s". %s' % (outputVal, outDimDict['domain'], tup)
                    outputDict['errorMessage'] = txt
                return outputDict
        else:
            outputDict = {
                'value': defaultValue,
                'errorMessage': 'input object length is not 3'
            }
            return outputDict
        
class TotalCoverageMatrixCoordinator:
    #An object that initializes and deals with Total Cover matrix.
    #It is a matrixt with 3 Inputs and 1 Output.
    def __init__(self, xlPath, shapeType = 'Point'):
        #ATTENTION!
        #in order for this matrix to be consistent with the exact same
        #strings provided in the excel table, always use field's ALIAS name.

        self.excelColumnNames = ['tmira', 'high', 'mid', 'TotalCoverage']

        #Notify in UI about process start:
        message = 'Creating total coverage matrix object: %s' % os.path.basename(xlPath)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)

        overwrite_original = arcpy.env.overwriteOutput
        arcpy.env.overwriteOutput = True
        #tblPath = os.path.join(arcpy.env.scratchGDB,"matrix")
        tblPath = os.path.join(arcpy.env.workspace,"matrix")
        arcpy.ExcelToTable_conversion(xlPath, tblPath)

        #Notify in UI about number of columns:
        Nrow = getFeatureCount(tblPath)
        message = 'Creating Total Cover matrix object: %s. Number of rows: %s' % (os.path.basename(xlPath), Nrow)
        arcpy.SetProgressor('default', message)
        arcpy.AddMessage(message)

        #Domains: import possible values.
        field_codes = {
            'Point':[40025,40035,40045,40120],
            'Polygon': [50047,50051,50055,50088]
        }
        inputFields_codes = field_codes[shapeType][:3]
        inputFields_domains = [fieldsDict[field_code].domain for field_code in inputFields_codes]
        self.inputDomains_possibilities = [listCodedValues(arcpy.env.workspace, domain) for domain in inputFields_domains]
        #Notify if a field is missing a domain OR the domain values are empty:
        for i,domainPossibilities in enumerate(self.inputDomains_possibilities):
            if len(domainPossibilities) == 0:
                fieldCode = inputFields_codes[i]
                fieldDomain = inputFields_domains[i]
                fieldName = fieldsDict[fieldCode].name
                workspace = arcpy.env.workspace
                txt = 'Domain "%s" of field "%s" is empty/not-found in workspace: "%s"' % (fieldDomain, fieldName, workspace)
                arcpy.AddWarning(txt)
        
        self.outputField_code = field_codes[shapeType][3]
        self.outputField_domain = fieldsDict[self.outputField_code].domain
        self.outputDomains_possibilities = listCodedValues(arcpy.env.workspace, self.outputField_domain)
        
        #This is the dict to be constructed in this __init__() method
        #and be availabe for use later:
        #{("input1", "input2", "input3"): "value"}
        self.coordinationDict = {}
        self.basename = os.path.basename(xlPath)
        
        #X- number of different values under "tmira".
        #Y- number of different values under "high".
        #Z- number of different values under "mid".
        x_set = set()
        y_set = set()
        z_set = set()

        #Construct self.coordinationDict using cursor:
        sc = arcpy.da.SearchCursor(tblPath, self.excelColumnNames)
        for r in sc:
            inputTup = r[:3]
            outputValue = r[3]

            #validate values:
            #Invalid values are values that appear in the excel file but not in domain.
            invalidValues_fieldIndecies = [i for i,v in enumerate(inputTup) if v not in self.inputDomains_possibilities[i]]
            invalid_fieldsAndValues = []
            for i in invalidValues_fieldIndecies:
                #called only if invalid value is found.
                columnName = self.excelColumnNames[i]
                invalidValue = inputTup[i]
                invalid_fieldsAndValues.append((columnName, invalidValue))
            if invalid_fieldsAndValues:
                txt = '--[total cover matrix] Value is not in domain: %s' % invalid_fieldsAndValues
                arcpy.AddWarning(txt)
            #end of validation.

            #add to dict
            self.coordinationDict[inputTup] = outputValue
            #add the column items to each set of possible values:
            x_set.add(inputTup[0])
            y_set.add(inputTup[1])
            z_set.add(inputTup[2])

        del sc
        
        self.keysByDimension = [list(s) for s in [x_set, y_set, z_set]]

        arcpy.env.overwriteOutput = overwrite_original
        arcpy.Delete_management(tblPath)
        arcpy.ResetProgressor()

    def solve(self, raw_values):
        outputDict = {
            'value': None,
            'errorMessage': None
        }
        tup = tuple(raw_values)
        defaultValue = "שגיאה"
        #1) length of tup must be 3:
        if len(raw_values) == 3:
            #2) check if all 3 values are among the options:
            # a list of 3 booleans, one for each dimension.
            conditions = [v in self.keysByDimension[i] for i,v in enumerate(tup)]
            falseIndices = [i for i,v in enumerate(conditions) if v is False]
            if falseIndices:
                dimensionNameAndValue = [f"{self.excelColumnNames[i]}: {tup[i]}" for i in falseIndices]
                dimensionNameAndValue_str = ', '.join(dimensionNameAndValue)
                outputDict = {
                    'value': defaultValue,
                    'errorMessage': 'The following values are not among the options: %s. Check table "%s"' % (dimensionNameAndValue_str, self.basename)
                }
                return outputDict
            else:
                #All of the values are valid, proceed.
                outputVal = self.coordinationDict[tup]
                outputDict['value'] = outputVal
                #If outputVal does not appear in the output field's domain:
                if len(self.outputDomains_possibilities)>0 and outputVal not in self.outputDomains_possibilities:
                    txt = 'Value "%s" does not appear in domain "%s". %s' % (outputVal, self.outputField_domain, tup)
                    outputDict['errorMessage'] = txt
                return outputDict
        else:
            outputDict = {
                'value': defaultValue,
                'errorMessage': '[total cover matrix] Number of values is not 3: %s' % str(raw_values)
            }
            return outputDict

class Node:
    def __init__(self, name = "", codedValue = "", altCode = ""):
        self.name = name
        self.codedValue = codedValue
        self.altCode = altCode
        self.value = 0
        self.children = []
        self.parent = None
    
    def __repr__(self):
        return "%s (%s): %s" % (self.name, self.codedValue, self.sumDown())

    def hasattribute(self, attributeName):
        return hasattr(self, attributeName)

    def findAndSet(self, codedValue, valueToSet):
        if self.codedValue == codedValue:
            self.value = valueToSet
            return
        for child in self.children:
            child.findAndSet(codedValue, valueToSet)
        
    def getValue(self):
        #attribute 'text' is superior to 'name'.
        if self.hasattribute('text'):
            return self.text
        else:
            return self.name

    def getNodesWithValue(self):
        """
        return a list of nodes with value higher than 0,
        among this node and any of its children.
        """
        arr = []
        findNodesAbove(self,0,arr)
        return(arr)

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

    def getLevel(self):
        level = 0
        p = self.parent
        while p:
            level += 1
            p = p.parent
        return level

    def hasChildren(self):
        return len(self.children) > 0

    def hasAlternative(self):
        """
        Returns true if node has alternative node to be converted to.
        (See class covertypeResult.convert()).
        """
        if self.altCode:
            return True
        else:
            return False

    def isEmpty(self):
        """
        Returns True if name and codedValue == ''.
        """
        if self.name == '' and self.codedValue == '':
            return True
        else:
            return False

    def printDown(self):
        #print(3 * "-" * self.getLevel() + "|" + self.name + " : " + str(self.codedValue) + " : " + str(self.sumDown()))
        print(3 * "-" * self.getLevel() + ">" + str(self.codedValue) + " : " + self.name)
        #if self.codedValue == None: self.codedValue = ""
        #print 3 * "-" * self.getLevel() + "|" + self.name + " : " + str(self.getLevel())
        if self.hasChildren():
            for c in self.children:
                c.printDown()

    def sumDown(self):
        s = self.value
        for c in self.children:
            s += c.sumDown()
        return s

    def resetValues(self):
        self.value = 0
        for child in self.children:
            child.resetValues()
    
    def asText(self):
        if self.matrixProduct:
            return self.matrixProduct
        else:
            return self.name

#PROCESS
arcpy.env.overwriteOutput = True
org = Organizer(
    input_stands,
    input_sekerpoints,
    sekerpoints_tables_relationships
)
fieldsDict = fieldsExcelToDict(fieldsExcel, fieldsExcel_sheet)
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

#speciesDict = speciesExcelToDict(speciesExcel) #deprecated
#speciesConversions = speciesExcelToDict1(speciesExcel) #deprecated

#Create species hierarchy:
root = Node()
arrayToTree(speciesHierarchy_jsonObject, root)
#create speciesDict based on root node:
speciesDict = createSpeciesDict(root, speciesHierarchy_path)
#Verify that every alternative code has a corresponding node in under root.
verifyAlternativeNodes(root, speciesDict)

#### Process section 0: ####
# Check fields exist and notify if not.
# Create new fields by sequence.

# 0.1: Change the field name of field 40000 - points object id
# (it won't always be "objectid"). Instead, look for the object id
# and assign it to code 40000.
fieldsDict[40000].name = getOidFieldName(org.sekerpoints.name)

# 0.2 Make sure stands fc have a GlobalID field,
# if it does not - create one based on field code 50024.
smallFieldObj = fieldsDict[50024]
message = 'Checking %s field.' % smallFieldObj.name
arcpy.SetProgressor('default', message)
arcpy.AddMessage(message)

if fieldsDict[50024].name.lower() not in [f.name.lower() for f in org.stands.desc.fields]:
    message = 'Field %s was not found in %s. Creating...' % (smallFieldObj.name, org.stands.name)
    arcpy.SetProgressor('default', message)
    arcpy.AddMessage(message)
    createBlankField(org.stands, smallFieldObj)

# 0.3 Check all the input fields exist (excel column checkIfExists)
#A1) First check fields of seker points:
fieldsToCheck = [x for x in fieldsDict.values() if hasattr(x,'code')]
missingFields = []

fieldsToCheck_sekerpoints = [x for x in fieldsToCheck if str(x.code)[:2] == '40' and x.checkIfExists]
fieldnames_sekerpoints = [f.name.lower() for f in org.sekerpoints.desc.fields]
for smallFieldObj in fieldsToCheck_sekerpoints:
    name = smallFieldObj.name.lower()
    if name not in fieldnames_sekerpoints:
        missingFields.append(smallFieldObj)

#A2) Second check fields of stands:
fieldsToCheck_stands = [x for x in fieldsToCheck if str(x.code)[:2] == '50' and x.checkIfExists]
fieldnames_stands = [f.name.lower() for f in org.stands.desc.fields]
for smallFieldObj in fieldsToCheck_stands:
    name = smallFieldObj.name.lower()
    if name not in fieldnames_stands:
        missingFields.append(smallFieldObj)

#B) Check fields of sekerpoints' related tables:
for relationshipClass in org.sekerpoints.relationships.values():
    destination = relationshipClass.destination
    prefix = str(destination.fieldCodesPrefix)
    if destination.desc.datasetType != 'Table':
        continue
    fieldsToCheck_relatedTable = [x for x in fieldsToCheck if str(x.code)[:2] == prefix and x.checkIfExists]
    fieldnames_relatedTable = [f.name.lower() for f in destination.desc.fields]
    for smallFieldObj in fieldsToCheck_relatedTable:
        name = smallFieldObj.name.lower()
        if name not in fieldnames_relatedTable:
            missingFields.append(smallFieldObj)

#C) Raise an ERROR if fields are missing:
#   e.g - CRASH the code here.
if missingFields:
    errorMessage = "One or more required fields are missing:"
    fieldsMessage = '\n'.join([fieldObj.asText() for fieldObj in missingFields])
    errorText = errorMessage + "\n" + fieldsMessage
    arcpy.AddError(errorText)

#D) Specifically check if sekerpoints has field TotalVitalCover.
#   If it does not - notify and create it.
fieldcode = 40118
hasOwnField = fieldsDict[fieldcode].name.lower() in \
[f.name.lower() for f in org.sekerpoints.desc.fields]
if not hasOwnField:
    smallFieldObj = fieldsDict[fieldcode]
    #notify:
    message = "Field '%s' does not exists in sekerpoints feature class '%s'." \
    % (smallFieldObj.name, org.sekerpoints.name)
    arcpy.AddMessage(message)
    #add field:
    createBlankField(org.sekerpoints, smallFieldObj)

del hasOwnField, fieldcode, smallFieldObj

#### Process section 1: ####
# Create related tables for stands FC,
# and relate them with stands FCs.

#Notify in UI about process start:
message = 'Creating relationship classes for stands FC'
relationshipsCount = len(stands_relatedTables)
arcpy.SetProgressor("step",message,0,relationshipsCount,1)
arcpy.AddMessage(message)

for nickname, tableDict in stands_relatedTables.items():
    #name - he basic name of the table. (InvasiveSpecies, PlantTypeCoverDistribut, etc...).
    tableIdentifier = tableDict['name']

    #UI notification:
    message = 'Creating relationship class: %s -> %s' % (org.stands.name, tableIdentifier)
    arcpy.SetProgressorLabel(message)

    #The table name: standsName_tableIdentifier
    tableName = "_".join([org.stands.name,tableIdentifier])
    #Field are made up of: 1) global fields 2) specific fields.
    fieldCodes = stands_relatedTables_globalFieldCodes + tableDict['fieldCodes']
    fieldObjects = [fieldsDict[fieldCode] for fieldCode in fieldCodes]
    #Create the table in the workspace (same workspace as Stands).
    #For now (19.9.2022), create a blank, new table, even if a table with the same name already exists.
    #E.g, overwrite.
    arcpy.AddMessage('Creating table: %s.' % tableName)
    createTable_result = arcpy.management.CreateTable(arcpy.env.workspace, tableName)
    #Create a FC out of the result object.
    newTable = FeatureClass(arcpy.Describe(createTable_result).catalogPath)
    #Add Fields:
    for fieldObject in fieldObjects:
        fName = fieldObject.name
        fAlias = fieldObject.alias
        fType = fieldObject.type
        fDomain = fieldObject.domain
        if fDomain:
            #If a field has a domain: check if it exists in stands GDB domains list, and if it does't add it.
            #NOTICE: the code checks existance of the domain in the GDB,
            #but DOES NOT check the codes and values of it.
            if not fDomain in org.stands.wsDomains:
                #A domain has been specified for this field, and is not exist in target GDB.
                arcpy.AddMessage('Importing domain: ' + fDomain)
                importDomain(fDomain, origin_GDB, org.stands.workspace)
        arcpy.AddMessage('\t-Adding field: %s, %s.' % (fName, fAlias))
        if fieldObject.length:
            arcpy.management.AddField(newTable.name, fName, fType, field_alias = fAlias, field_domain = fDomain, field_length = fieldObject.length)
        else:
            arcpy.management.AddField(newTable.name, fName, fType, field_alias = fAlias, field_domain = fDomain)
    #After adding fields, relate the table to stand FC.
    """
    Nickname of the relationship, represents the relationship class and its
    function in the code. Stays constant and independent of featureclasses'
    or tables' names, so using it is favorable.
    """
    #The first field of global fields is used for linkage.
    destinationKey = fieldObjects[0].name
    newRelationship_desc = createRelation(org.stands, "GlobalID", newTable, destinationKey)
    relationshipClass = RelationshipClass(newRelationship_desc.name, nickname, org.stands)
    org.relationships[nickname] = relationshipClass
    arcpy.SetProgressorPosition()
arcpy.ResetProgressor()

#### Process section 2: ####
# Relate stands FC and seker points FC using stand's global ID.

#Notify in UI about process start:
message = 'Creating relationship: %s -> %s' % (org.stands.name, org.sekerpoints.name)
relationshipsCount = len(stands_relatedTables)
arcpy.SetProgressor("default",message)
arcpy.AddMessage(message)

# Use a single for-loop to make the code less scary:
for indexThatWontBeUsed in [1]:
    # @Notice: for now the field names are NOT taken from the excel,
    # and are hard-coded.

    #Add stand_ID field and update forest address fields of sekerpoints.
    #Use a temporary FC - the output of spatial join geoprocessing.
    #tempSpatialJoin_fullpath = os.path.join(arcpy.env.workspace, "tempSJ")
    tempSpatialJoin_fullpath = os.path.join("in_memory", "tempSJ__")

    #for debug:
    #print(arcpy.env.scratchGDB)

    # Field mapping for the spatial join tool,
    # allows full control on output fields.
    fieldMappings = arcpy.FieldMappings()
    fieldMaps = []

    for fName in forestAddressFieldNames:
        fm = arcpy.FieldMap()
        fm.addInputField(org.stands.name, fName)
        fieldMaps.append(fm)

    #Stand ID needs a special handling:
    fm_id = arcpy.FieldMap()
    fm_id.addInputField(org.stands.name, standID_field['inputField'])
    outputfield = fm_id.outputField
    outputfield.name = standID_field['name']
    outputfield.aliasName = standID_field['aliasName']
    outputfield.type = standID_field['type']
    outputfield.isNullable = standID_field['isNullable']
    fm_id.outputField = outputfield
    fieldMaps.append(fm_id)

    #Append ID field to the names of the others:
    forestAddressFieldNames.append(standID_field["name"])

    for fm in fieldMaps:
        fieldMappings.addFieldMap(fm)

    #UI notification:
    message = 'Spatial join'
    arcpy.SetProgressorLabel(message)
    arcpy.AddMessage(message)

    arcpy.analysis.SpatialJoin(
        org.sekerpoints.name,
        org.stands.name,
        tempSpatialJoin_fullpath,
        "JOIN_ONE_TO_MANY",
        "KEEP_ALL",
        fieldMappings,
        "INTERSECT",
    )

    tempSJ = FeatureClass(tempSpatialJoin_fullpath)

    #Before writing to sekerpoints using UpdateCursor,
    #check the fields exist.
    #Notice: the NAME might be identical, but the type must be the same too.
    for fieldName in forestAddressFieldNames:
        if fieldName.lower() not in [field.name.lower() for field in org.sekerpoints.desc.fields]:
            importField(tempSJ, org.sekerpoints, fieldName)

    #UI notification:
    message = 'Update relationship fields'
    arcpy.SetProgressorLabel(message)
    arcpy.AddMessage(message)

    #Write to sekerpoints:
    sp_uc = arcpy.UpdateCursor(org.sekerpoints.name)
    for sp_r in sp_uc:
        id = sp_r.getValue(org.sekerpoints.oidFieldName)
        #Create a query for SJ FC:
        #Based on: "TARGET_FID (of temp SJ) == object id (of sekerpoint)".
        field_delimited = arcpy.AddFieldDelimiters(tempSJ.workspace, "TARGET_FID")
        sql_exp = """{0} = {1}""".format(field_delimited, id)
        temp_sc = arcpy.SearchCursor(tempSJ.fullPath, where_clause = sql_exp)
        temp_r = temp_sc.next()
        for fname in forestAddressFieldNames:
            #Notice: stand id field has been appended.
            sp_r.setValue(fname, temp_r.getValue(fname))
        del temp_sc
        sp_uc.updateRow(sp_r)
    del sp_uc

    arcpy.management.Delete(tempSJ.fullPath)
    del tempSJ

    #UI notification:
    message = 'Creating relationsip'
    arcpy.SetProgressorLabel(message)
    arcpy.AddMessage(message)

    #Relate stands and sekerpoints
    nickname = 'sp'
    newRelationship_desc = createRelation(org.stands, "GlobalID", org.sekerpoints, standID_field['name'])
    relationshipClass = RelationshipClass(newRelationship_desc.name, nickname, org.stands)
    org.relationships[nickname] = relationshipClass

    arcpy.ResetProgressor()

#### Process section 3: ####
# Add blank fields to stands FC by sequence.
# Or move fields with their values by sequence.
if addFields:
    #Find the relevant fields, based on 'toAdd' attribute:
    fieldsToHandle = set()
    for sf in fieldsDict.values():
        #Not all values have these attributes.
        if hasattr(sf,'toAdd') and hasattr(sf,'code'):
            #Checks: 1)need to add, and 2)belongs to 'sekerpoints':
            if sf.toAdd and str(sf.code)[:2] == '50':
                fieldsToHandle.add(sf)
    #sort fieldsToHandle by sequence:
    fieldsToHandle = list(fieldsToHandle)
    fieldsToHandle.sort(key = lambda x: (x.sequence, x.code))

    #Notify in UI about process start:
    message = 'Adding output fields to: %s.' % org.sekerpoints.name
    fieldsCount = len(fieldsToHandle)
    arcpy.SetProgressor("step",message,0,fieldsCount,1)
    arcpy.AddMessage(message)

    counter = 1
    for smallFieldObj in fieldsToHandle:
        tempMessage = message + " (%s of %s)" % (counter, fieldsCount)
        arcpy.SetProgressorLabel(tempMessage)

        arcpy.AddMessage('\t-Adding field: %s, %s.' % (smallFieldObj.name, smallFieldObj.alias))
        #Fields should be either:
        # 1) created blank,
        # or
        # 2) moved to their place by sequence, keeping their values.
        if smallFieldObj.toAdd == 'keepValues':
            globalID_fieldObj = fieldsDict[50024]
            moveFieldToEnd(org.stands, smallFieldObj, globalID_fieldObj)
        elif smallFieldObj.toAdd == 'blank':
            createBlankField(org.stands, smallFieldObj)

        arcpy.SetProgressorPosition()
        counter += 1
    del counter, tempMessage
    arcpy.ResetProgressor()

#### Process section 4: ####
# Create Matrices: 
# Must run after creation of fields.
forestVegFormCoordinator = MatrixCoordinator(forestVegFormExcel)
standVegFormCoordinator = MatrixCoordinator(standVegFormExcel)
speciesCompositionCoordinator = MatrixCoordinator(speciesCompositionExcel)
relativeDensityKeyCoordinator = Matrix3DCoordinator(relativeDensityKeyExcel)
totalCoverageCoordinator = TotalCoverageMatrixCoordinator(totalCoverageExcel, org.stands.shapeType)


#### Process section 5: ####
# Go through each stand polygon: 

#Notify in UI about process start:
message = 'Calculating...'
featureCount = getFeatureCount(org.stands.name)
arcpy.SetProgressor("step",message,0,featureCount,1)
arcpy.AddMessage(message)
counter = 1

stands_uc = arcpy.UpdateCursor(
    org.stands.name,
    #where_clause = 'OBJECTID IN (67, 168, 331, 369, 268)', #for debug!!!
    sort_fields = "%s A" % org.stands.oidFieldName
    )
#Main iteration:
for stand_r in stands_uc:
    tempMessage = 'Calculating... (row: %s of %s feafures)' % (counter, featureCount)
    arcpy.SetProgressorLabel(tempMessage)

    standObj = StandPolygon(stand_r, org.stands)
    stands_uc.updateRow(standObj.row)

    arcpy.SetProgressorPosition()
    counter += 1
del stands_uc
print('done')