# -*- coding: utf-8 -*-
#CLASSIFICATION VERSION 03.2024
import os
import arcpy
import json
import math
import datetime
from collections import Counter

import arcpy.management



#TOOL PARAMETERS
debug_mode = False
addFields = True
if debug_mode:
    #debug parameters
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\QA\8.2.2025 - unite stands\smy_survey_Alonim_BKP_270724.gdb'
    input_sekerpoints = os.path.join(input_workspace, 'smy_survey_Alonim')
    input_configurationFolder = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\עבודה\configuration'
    input_beitGidul = "צחיח-למחצה" #ים-תיכוני
else:
    input_sekerpoints = arcpy.GetParameter(0)
    #Take all the features, even if layar has selection.
    input_sekerpoints = arcpy.Describe(input_sekerpoints).catalogPath
    input_configurationFolder = arcpy.GetParameterAsText(1)
    input_beitGidul = arcpy.GetParameterAsText(2)


#VARIABLES
sekerpoints_tables_relationships = {
    #'nickname': ('name of relationship class', field codes prefix <int>),
    'pt1': (os.path.basename(input_sekerpoints) + '_InvasiveSpecies', 41),
    'pt2': (os.path.basename(input_sekerpoints) + '_PlantTypeCoverDistribut', 42),
    'pt3': (os.path.basename(input_sekerpoints) + '_StartRepeatDominTree', 43),
    'pt4': (os.path.basename(input_sekerpoints) + '_VitalForest', 44),
}
fieldsExcel = os.path.join(input_configurationFolder, 'fields.xlsx')
fieldsExcel_sheet = 'classification'

forestVegFormExcel = os.path.join(input_configurationFolder, 'ForestVegForm.xlsx')
standVegFormExcel = os.path.join(input_configurationFolder, 'StandVegForm.xlsx')
speciesCompositionExcel = os.path.join(input_configurationFolder, 'species composition.xlsx')
relativeDensityKeyExcel = os.path.join(input_configurationFolder, 'relativeDensityKey.xlsx')
totalCoverageExcel = os.path.join(input_configurationFolder, 'TotalCoverage.xlsx')

origin_GDB = os.path.join(input_configurationFolder, 'origin.gdb')

speciesHierarchy_path = os.path.join(input_configurationFolder, 'speciesHierarchy.json')
with open(speciesHierarchy_path, encoding='utf-8') as f:
    speciesHierarchy_jsonObject = json.load(f)

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

subCoverType_domain = [
    #This domain is in descending order.
    #YOU CAN CHANGE THE TEXTS BUT DO-NOT CHANGE THE ORDER, OMIT OR ADD.
    #(for example: 'עצים' will keep its index and logic functionality.)
    "שיחים",
    "בני_שיח",
    "עשבוני",
    "עצים",
    "ללא_כיסוי",
]

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

presenceConifer_threshold = {
    "נטיעה": 4,
    "התחדשות_טבעית": 5
}
presenceConifer_domain = [
    "",
    None,
    "אין",
    "1-20",
    "21-50",
    "51-100",
    "מעל 100"
]

presenceBroadleaf_threshold = {
    "נטיעה": 4,
    "התחדשות_טבעית": 6
}
presenceBroadleaf_domain = [
    "",
    None,
    "אין",
    "1-5",
    "6-10",
    "11-20",
    "מעל 20"
]

beitgidulList = [
    "ים-תיכוני",
    "ים-תיכוני יבש",
    "צחיח-למחצה"
]

#FUNCTIONS
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

def importDomain(domainName, sourceGDB, destinationGDB):
    """
    Checks if a domain exists in source GDB and imports it to destination GDB.
    """
    source_domains = arcpy.Describe(sourceGDB).domains
    destination_domains = arcpy.Describe(destinationGDB).domains
    if not domainName in source_domains:
        #If the desired domain is not in source GDB → warn, don't add it, continue and CREATE FIELD w/o domain.
        arcpy.AddWarning('Could not import domain "%s", from GDB: "%s". Field will be created without assigning this domain.' % (domainName, sourceGDB))
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

def getFeatureCount(feature):
    return int(arcpy.management.GetCount(feature)[0])

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

def findNodesAbove(node,val,array):
    #Appends to array every node that its value is above val.
    if node.value>val:
        array.append(node)
    for child in node.children:
        findNodesAbove(child,val,array)

def isOrIsChildOf(inputNode, inputName):
    """
    Returns True if the input node, or any of its parents,
    has the inputName as their name (a node's attribute). 
    """
    nodeName = inputNode.name
    if nodeName == inputName:
        return True
    elif inputNode.parent:
        return isOrIsChildOf(inputNode.parent, inputName)
    else:
        return False

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
        
        if debug_mode:
            if code in dic.keys():
                print('Code [%s] appears more than once. node: %s (%s).' % (code, node.name, node.codedValue))
            if name in dic.values():
                print('Name [%s] appears more than once. node: %s (%s).' % (name, node.name, node.codedValue))
        
        dic[code] = name
    except ValueError as e:
        #print (node.codedValue, e)
        pass
    for child in node.children:
        createSpeciesDict_rec(child, dic)

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

def average(aList):
    return sum(aList)/len(aList)

def groupByValue(input_list, groupValue_index):
    """
    Takes a list of tuples, returns a dict with a key for every group value.
    Example:
    - input_list: [(a1,b1,c1), (a2,b2,c1), (a13,b12,c5)...], groupValue_index = 2
    - output: {c1: [(a1,b1,c1), (a2,b2,c1), ...],
               c5: [(a13,b12,c5), ...], ...}
    """
    outDict = {}
    for tup in input_list:
        groupValue = tup[groupValue_index]
        if groupValue in outDict.keys():
            outDict[groupValue].append(tup)
        else:
            outDict[groupValue] = [tup]
    return outDict

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

class Organizer:
    #An object that holds data models.
    def __init__(self, sekerpoints, sekerpointsRelationships):
        self.sekerpoints = FeatureClass(sekerpoints)
        """
        #Coordinate system of both FCs must be the same.
        self.checkSR([self.stands, self.sekerpoints])
        if self.stands.workspace != self.sekerpoints.workspace:
            arcpy.AddError('Stands and seker points are not in the same workspace.')
        """
        arcpy.env.workspace = self.sekerpoints.workspace
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

class SekerPoint(FcRow):
    def __init__(self, row, sekerpointsFC):
        FcRow.__init__(self, row, sekerpointsFC)
        arcpy.AddMessage('Started calculating: sekerpoint %s = %s'% (self.FC.oidFieldName, self.id))
        self.notifier = Notifier(self, 40113)

        # DEPRECATED (validation of related row's creation time)
        #self.validateTimeDuplications()

        self.importSpecies()
        self.planttype = self.importPlantType()

        #Construct layers
        self.layers = {
            'tmira': ForestLayer(self, 4),
            'high': ForestLayer(self, 3),
            'mid': ForestLayer(self, 2),
            'sub': SubForestLayer(self)
        }
        
        self.validateRelatedRows()
        self.validate()

        self.calculateAndWrite()
        self.notifier.write()

    def calculateAndWrite(self):
        """
        An module that runs calculation methods (c__...) and
        writes their results into stand row, or its related
        tables.
        """
        """
        The following attributes with the prefix "v__" for VALUE of calculations.
        The rest of the name, after the prefix, after the field name.
        """
        #1+2)LOGIC LAYERS:
        self.v__logiclayers = self.c__logiclayers()
        oedered_fieldCodes = {
            #order: [forest layer, veg form, layer cover, layer desc]
            'primary': [40103,40104,40105,40102],
            'secondary': [40107,40108,40109,40106]
        }
        for order, layerResult in self.v__logiclayers.items():
            #oeder is the key of the result dict, can be primary/secondary
            #to fit the keys fieldCodes.
            fieldCodes = oedered_fieldCodes[order]
            values = layerResult.getValuesToWrite()
            self.writeSelf(fieldCodes, values)

        #3)FOREST VEGFORM:
        self.v__forestvegform = self.c__forestvegform(self.v__logiclayers)
        self.writeSelf(40110, self.v__forestvegform)

        #4)SPECIES COMPOSITION:
        self.v__covtype = self.c__covtype(
            self.v__logiclayers
        )
        self.writeSelf(40111, self.v__covtype.str)

        #5)GROUND LEVEL FLOOR VEGFORM:
        self.v__groundlevelfloorvegform = self.c__groundlevelfloorvegform()
        self.writeSelf(40119, self.v__groundlevelfloorvegform)

        #6)TOTAL VITAL COVER:
        self.v__forestdegeneration = self.c__forestdegeneration()
        self.writeSelf(40118, self.v__forestdegeneration)

        #7)TREE HARM:
        self.v__treeharm = self.c__treeharm()
        self.writeSelf(40114, self.v__treeharm)

        #8)RELATIVE DENSITY:
        self.v__relativedensity = self.c__relativedensity(
            input_beitGidul
            )
        self.writeSelf(40116, self.v__relativedensity)

        #9)TOTAL COVERAGE:
        self.v__totalcoverage = self.c__totalcoverage()
        self.writeSelf(40120, self.v__totalcoverage)

        #10)FOREST AGE COMPOSITION:
        self.v__forestagecomposition = self.c__forestagecomposition()
        self.writeSelf(40019, self.v__forestagecomposition)

        #11)DESCRIPTION FIELDS OF RELATED TABLES:
        self.v__invasivespecies_desc = self.c__invasivespecies_desc()
        self.writeSelf(40123, self.v__invasivespecies_desc)
        
        self.v__vitalforest_desc = self.c__vitalforest_desc()
        self.writeSelf(40121, self.v__vitalforest_desc)
        self.v__planttype_desc = self.c__planttype_desc()
        self.writeSelf(40122, self.v__planttype_desc)

        return

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
        #First - check if the field has any value and keep it if it does.
        rawValue = self.getSelfValue(40019)
        unwantedValues = [None, '']
        if rawValue not in unwantedValues:
            #Keep the field's original value.
            return rawValue
        else:
            #indexed list of options to return:
            optionsToReturn = [
                "אין קומת עצים",
                "חד שכבתי",
                "דו שכבתי",
                "רב שכבתי",
            ]
            layerCoverKeys = list(layerCover_table1.keys())
            thrasholdIndex = 2

            rawValues = self.getSelfValue([40025,40035,40045])
            #Keep only values that can be indexed later.
            validValues = []
            for rawValue in rawValues:
                if rawValue in layerCoverKeys:
                    validValues.append(rawValue)
            
            indexedValues = [layerCoverKeys.index(v) for v in validValues]
            N_valuesAboveThreshold = len([index_ for index_ in indexedValues if index_ >= thrasholdIndex])
            return optionsToReturn[N_valuesAboveThreshold]

    def c__relativedensity(self, beitgidul):
        """
        Takes beitGidul, general density, forest age
        and use it to solve 3D matrix of relative density.
        """
        stepName = 'relativedensity'
        generaldensity_fieldCode = 40020
        coniferForestAge_fieldCode = 40022

        generaldensity = self.getSelfValue(generaldensity_fieldCode)
        agegroup = self.getSelfValue(coniferForestAge_fieldCode)

        #validate general density and age group.
        #and if both okay proceed to the main logic.
        if generaldensity is None:
            fName = fieldsDict[generaldensity_fieldCode].name
            fAlias = fieldsDict[generaldensity_fieldCode].alias
            txt = 'Found <null> in field "%s", "%s".' % (fName, fAlias)
            self.notifier.add(stepName, 'warning', txt)
            return None
        elif agegroup is None:
            fName = fieldsDict[coniferForestAge_fieldCode].name
            fAlias = fieldsDict[coniferForestAge_fieldCode].alias
            txt = 'Found <null> in field "%s", "%s".' % (fName, fAlias)
            self.notifier.add(stepName, 'warning', txt)
            return None
        else:
            #The main logic:
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

    def c__logiclayers(self):
        """
        Calculates sekerpoint's primary and secondary layers' attributes:
        forest layer, veg form, layer cover, layer desc.

        """
        stepName = 'logiclayers'
        #The method returns outDict
        outDict = {
            "primary": LayerResult(),
            "secondary": LayerResult()
        }

        #These are layer nums (4-1) that were assigned during classification of
        #primary and secondary layers:
        #(in order not to re-assign them)
        layerNumsToInvestigate = []

        validLayers = [layer for layer in self.layers.values() if layer.isValid]
        validLayers.sort(key=lambda x: x.layerNum, reverse = True)
        for threshold_layerCoverNum in [3,2]:
            for layer in validLayers:
                #Before inspecting, make sure there is room to insert
                #more layers to outDict:
                roomForAssignment = False in [layer.assigned for layer in outDict.values()]
                if (layer.layerNum in [4,3,2]) and roomForAssignment:
                    #convert cover <str> to coverNum <int>:
                    if layer.layerCover_num >= threshold_layerCoverNum and\
                        layer.layerNum not in layerNumsToInvestigate:
                        #insert it as primary or secondary layer:
                        if not outDict['primary'].assigned:
                            outDict['primary'].assignLayer(layer, True)
                            layerNumsToInvestigate.append(layer.layerNum)
                        elif not outDict['secondary'].assigned:
                            outDict['secondary'].assignLayer(layer, False)
                            layerNumsToInvestigate.append(layer.layerNum)
        
        #Sub-forest inspection:
        #Assign and set vegForm of sub-forest layer, in a way
        #that is different from the forest layers.
        #Make sure there is room to insert
        #more layers to outDict:
        roomForAssignment = False in [layer.assigned for layer in outDict.values()]
        if roomForAssignment:
            inspectedLayer = self.layers['sub']
            #Get the vecant layer order to assign to:
            for order in ['primary', 'secondary']:
                if not outDict[order].assigned:
                    layerOrder = order
                    break
            #Replicate self.planttype to a local variable that is
            #not referenced, because its values might get changed.
            planttype = {k:v for k,v in self.planttype.items()}
            #lowForest booleans, self-describing:
            lowForest_boolList = [inspectedLayer.isConiferForest, inspectedLayer.isBroadleafForest]
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

    def c__forestvegform(self, logiclayersDict):
        """
        Takes the output of c__logiclayers() method:
        - logiclayersDict: a dict of 'primary' & 'secondary' layer reselt objects.
        Calculates and returns veg form of the sekerpoint based on its
        calculated primary and secondary layers' veg form and layer cover.
        Returns <str>.
        """
        stepName = 'forestvegform'
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
      
    def c__covtype(self, logiclayersObj):
        """
        - logiclayersObj: output dict of c__logiclayers {
            'primary': LayerResult,
            'secondary': LayerResult
            }
        """
        stepName = 'covtype'

        primaryLayer = logiclayersObj['primary']
        secondaryLayer = logiclayersObj['secondary']

        #covtypeList was already integrated into root previously in __init__(),
        #unlike c__covtype in "unitepoints".

        #create a result object for covtype:
        resultObj = CovtypeResult(self, speciesCompositionCoordinator, forestVegFormCoordinator)

        if self.unidentified_found:
            return resultObj

        iterableNodes = root.getNodesWithValue()

        if len(iterableNodes) == 0:
            return resultObj

        #LOGIC START:
        """
        #check if covtype_old fields ([50098, 50099]) are:
        # "מחקר" and 9970, respectively.
        # @ NOTICE- "מחקר" has a DIFFERENT code from 9970.
        if self.getSelfValue([50098,50099]) == ["מחקר", "9970"]:
            resultObj.assignStudy()
            #return. that means the logic ends here.
            return resultObj
        """

        if not primaryLayer.isForestLayer:
            """
            Assigns the layer of subforest.
            Notice: covtype can only be one of the following:
            שיחייה, בתה, עשבוני, צומח גדות נחלים
            and can not be:
            יער נמוך (any of its options)
            so, in case primary layer is יער נמוך the code will
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
                planttype = {k:v for k,v in self.planttype.items()}
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
                #take vegform from all forest layers (high, t, m), not only primary and secondary!
                forestLayer_vegForms_numsFields = {4:40024, 3:40034, 2:40044}
                vegForms = set()
                for layerNum in [4, 3, 2]:
                    fieldcode = forestLayer_vegForms_numsFields[layerNum]
                    forestVegForm_raw = self.getSelfValue(fieldcode)
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
                #take vegform from all forest layers (high, t, m), not only primary and secondary!
                forestLayer_vegForms_numsFields = {4:40024, 3:40034, 2:40044}
                vegForms = set()
                for layerNum in [4, 3, 2]:
                    fieldcode = forestLayer_vegForms_numsFields[layerNum]
                    forestVegForm_raw = self.getSelfValue(fieldcode)
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
                    self.notifier.add(stepName, 'warning', txt)

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
        txt = "Could not determine species composition."
        self.notifier.add(stepName, 'warning', txt)
        resultObj.str = "Could not determine."
        return resultObj

    def c__groundlevelfloorvegform(self):
        """
        Calculates stand's ground level floor veg form based on:
            -self.layers['sub'].isConiferForest <bool>
            -self.layers['sub'].isBroadleafForest <bool>
            -planttype <dict>
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

        #Replicate self.planttype to a local variable that is
        #not referenced, because its values might get changed.
        planttype = {k:v for k,v in self.planttype.items()}
        #lowForest booleans, self-describing:
        isConiferForest = self.layers['sub'].isConiferForest
        isBroadleafForest = self.layers['sub'].isBroadleafForest
        lowForest_boolList = [isConiferForest, isBroadleafForest]
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

    def c__forestdegeneration(self):
        """
        Checks if field 'totalVitalCover' has value.
        If it has - return it. If it does not have - return the maximal value from
        related table 'vitalForest'.
        """
        rawValue = self.getSelfValue(40118)
        unwantedValues = [None, '']
        if rawValue not in unwantedValues:
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
            #remove unwantedValues:
            for unwantedValue in unwantedValues:
                while unwantedValue in values: values.remove(unwantedValue)
            #sort descending by percentValues_sorted:
            values.sort(key= lambda x: percentValues_sorted.index(x), reverse = True)
            if values:
                return values[0]
            else:
                return defaultValue
    
    def c__totalcoverage(self):
        """
        Checks if field 'totalCoverage' has value.
        If it has - return it.
        If it does not - take values of all 3 cover layers and solve a matrix.
        """
        stepName = 'totalcoverage'
        rawValue = self.getSelfValue(40120)
        unwantedValues = [None, '']
        if rawValue not in unwantedValues:
            return rawValue
        else:
            forestLayerCovers = [l.layerCover for l in self.layers.values() if l.isForestLayer]
            #Replace '' or None with 'אין' for the calculation:
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
            
    def c__treeharm(self):
        """
        Takes values of 4 fields, convets each one to
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

        harmsList = self.getSelfValue([40059, 40060, 40061, 40062])

        #notice: items of harmsList can be either one of domainValues.keys() or None.
        #Remove None from harmsList:
        while None in harmsList:
            harmsList.remove(None)
        #convert category to ceil of avg:
        averagesList = [domainValues[category][0] for category in harmsList]
        #Sum. if len(averagesList) == 0: sum = 0.
        averagesSum = sum(averagesList)
        #Notify in case averagesSum > 100:
        if averagesSum>100:
            txt = 'sum of harms averages > 100. Items: %s' % str(harmsList)
            self.notifier.add(stepName, 'warning', txt)
        #convert to categoryand return:
        category = toCategory(min(averagesSum, 100), backwardsList)
        return category

    def __repr__(self):
        return "SekerPoint object, id = %s" % self.id

    def importPlantType(self):
        """
        Return Plant Type Cover distribution based on values in 
        each point's PlantTypeCoverDistribut related table.
        Steps:
        1) populate with existing values.
        2) supllement to "ללא כיסוי" if necessary until sum == 100%
        Returns: a dictionary {plant type <str>: cover percent <int>}
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

        for plantType, percent in rawValues:
            #Handle values of percent.
            # *see classification script SubForestLayer.subForestCover()
            if percent in [None, "", "0%"]:
                percent = 0
            else:
                percent = int(percent.replace("%",""))
            
            #Handle values of plant type that are not in plantTypeDict.keys():
            #→warn and skip to next row.
            if (plantType not in plantTypeDict.keys()) or (plantType is None):
                txt = "Plant type of subforest is not valid: %s." % plantType
                self.notifier.add(stepName, 'warning', txt)
                continue

            #assign values in a cumulative way:
            plantTypeDict[plantType] += percent

        
        #notify in case any value is over 100:
        badValues = ', '.join([f"{k}: {v}" for k,v in plantTypeDict.items() if v>100])
        if badValues:
            txt = 'Value is over 100: %s. Please check table planttypecoverdistribut.' % badValues
            self.notifier.add(stepName, 'warning', txt)

        #supllement to "ללא כיסוי" if necessary until sum == 100%
        percentSum = sum(plantTypeDict.values())
        sumIsAMultipleOfTen = percentSum%10 == 0
        if not sumIsAMultipleOfTen:
            #a rare case → add ERROR.
            txt = "Sum of subforest plant type is not a multiple of 10. SekerPoint %s: %s." % (self.FC.oidFieldName, self.id)
            self.notifier.add(stepName, 'error', txt)
            return None
        elif percentSum < 100:
            #warn:
            txt = "Sum of subforest plant type is less than 100. SekerPoint %s: %s." % (self.FC.oidFieldName, self.id)
            self.notifier.add(stepName, 'warning', txt)
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
        if rawValue not in (None, ''):
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

    def validate(self):
        """
        Validation of this current row.
        1) sum of species is not 10 - or - sum of species is 0.
        2) unidentified species.
        patches:
        1) find vegform fields with more than 2 veg forms.
        """
        stepName= 'validate - sum of species'
        sumOfSpecies = root.sumDown()
        if sumOfSpecies == 0:
            txt = 'Sum of species equals 0.'
            self.notifier.add(stepName, 'warning', txt)
        elif sumOfSpecies != 10:
            txt = 'Sum of species is not 10.'
            self.notifier.add(stepName, 'warning', txt)

        stepName= 'validate - unidentified species'
        #Add a variable to indicate logic for self.c__covtype().
        self.unidentified_found = False
        #unidentifiedNodes_toNotify: a list of [Nodes, ]
        #that contains only cases for which a warning should be posted,
        #not every case of "unidentified" or its children.
        unidentifiedNodes_toNotify = []
        valuableNodes = []
        outliers_codes = ['9990','9992','9993']
        findNodesAbove(root,0,valuableNodes)
        for node in valuableNodes:
            if isOrIsChildOf(node, "unidentified"):
                if node.codedValue in outliers_codes and node.value == 10:
                    #No need to nofity
                    continue
                else:
                    unidentifiedNodes_toNotify.append(node)
        if unidentifiedNodes_toNotify:
            self.unidentified_found = True
            nodesRepresentation_list = ["%s(%s):%s"%(n.name, n.codedValue, n.value) for n in unidentifiedNodes_toNotify]
            nodesRepresentation = ', '.join(nodesRepresentation_list)
            txt = 'Contains "unidentified" species or one of its subgroups: %s.' % nodesRepresentation
            self.notifier.add(stepName, 'warning', txt)
        
        #PATCHES:
        #find vegform fields with more than 2 veg forms.
        stepName= 'validate - vegform count'
        vegform_fieldCodes = {
            "tmira": 40024,
            "high": 40034, 
            "mid": 40044
            }
        for fieldCode in vegform_fieldCodes.values():
            smallFieldObj = fieldsDict[fieldCode]
            rawValue = self.getSelfValue(fieldCode)
            if hasattr(rawValue, 'split') and rawValue not in ['', ' ']:
                splitValues = rawValue.split(',')
                """
                #remove spaces from list:
                valuesToRemove = ['', ' ']
                for valueToRemove in valuesToRemove:
                    while valueToRemove in splitValues:
                        splitValues.remove(valueToRemove)
                """
                if len(splitValues) >= 3:
                    txt = 'veg form >=3 [field: %s %s]' % (smallFieldObj.code, smallFieldObj.alias)
                    self.notifier.add(stepName, 'warning', txt)
            else:
                continue

        return
    
    def validateRelatedRows(self):
        """
        Validate point's 4 related tables for:
        1) Duplications, 
        2) Missing values (null).
        
        Two fields in every table:
        1st - checked for duplications AND missing values.
        2nd - checked for missing values only.
        """
        stepName = 'validateRelatedRows'

        warning_messages = [
            "Double record in the table",
            "Missing record in the table"
        ]

        # first field - checked for duplicaions AND missing values
        # second field - checked for missing values.
        #(relation nickname, field1, field2)
        fields = [
            ('pt1', 41002, 41003),
            ('pt2', 42002, 42003),
            ('pt3', 43005, 43006),
            ('pt4', 44002, 44003)
        ]

        for nickname, field1, field2 in fields:
            rawData = self.getRelatedValues(nickname, [field1, field2])
            values_1 = [r[0] for r in rawData]
            values_2 = [r[1] for r in rawData]
            tableName = org.relationships[nickname].destination.name
            # Duplications - first field:
            duplications_found = len(values_1) - len(removeDup(values_1)) != 0
            if duplications_found:
                txt = f"{warning_messages[0]} {tableName}"
                self.notifier.add(stepName, 'warning', txt)
            # Missing values - both fields:
            missing_found = None in values_1 + values_2
            if missing_found:
                txt = f"{warning_messages[1]} {tableName}"
                self.notifier.add(stepName, 'warning', txt)


        return

    def importSpecies(self):
        """
        A method that imports pair-wise data from startRepeatDominTree related table,
        and constructs root object with it's relevant data.
        """
        stepName = 'importSpecies'
        root.resetValues()
        #dictionary of {codedValue<'str'>: proportion <int>, ...}
        outdict = {}
        species_raw = self.getRelatedValues('pt3',[43005, 43006])
        for codedValue, proportion in species_raw:
            #Handle values of proportion and convert to integer.
            if proportion in [None, "", "0%"]:
                proportion = 0
            
            #Handle a situation in which: (28/8/2022)
            #Coded value does not exist AND proportion DOES exist:
            if (codedValue in [None, ""]) and proportion > 0:
                txt = 'Proportion > 0 while species does not exist.'
                self.notifier.add(stepName, 'warning', txt)
                continue

            #Handle a situation in which: (5/9/2022)
            #The same species code (codedValue) appears more than once.
            if codedValue in outdict.keys():
                txt = 'Species %s appears more than once.' % codedValue
                #SUSPEND notification because duplication is validated elsewhere (validateRelatedRows).
                #self.notifier.add(stepName, 'warning', txt)
            
            #Assign values into outdict + root.
            outdict[codedValue] = int(proportion)
            root.findAndSet(codedValue, int(proportion))
        return

    def validateTimeDuplications(self):
        """
        Validation of rows in related tables for duplications before importing.
        Process: get related values, group rows by creation time. If there is
        more than 1 creation time group check validity for the latest time group, 
        and if valid, delete all other time groups' rows. If not valid - proceed 
        to the next latest time group and so on. If all of the groups are invalid
        notify and don't delete any.
        The tool does a similar process for two tables:
        - PlantTypeCoverDistribut ['pt2']
        - StartRepeatDominTree ['pt3']
        """
        stepName = 'validateTimeDuplications - PlantTypeCoverDistribut'
        #Import values and group by creation time:
        #[(plantType, percentByTen, creationDate), ...]
        rawValues = self.getRelatedValues('pt2',[42002,42003,42005])
        groupedValues = groupByValue(rawValues, 2)
        #Get a list of all the time values and sort it:
        times = list(groupedValues.keys())
        if len(times) > 1:
            times = sorted(times, reverse=True)
            selectedTime = None
            for inspectedTime in times:
                rows = groupedValues[inspectedTime]
                #Inspect two conditions:
                #Condition 1: no duplications of plantType
                #Condition 2: sum of percentage >= 100
                plantTypes = []
                percents = []
                for plantType, percent, t in rows:
                    plantTypes.append(plantType)
                    if percent in [None, "", "0%"]:
                        percents.append(0)
                    else:
                        percents.append(int(percent.replace("%","")))
                condition_1 = len(plantTypes) - len(removeDup(plantTypes)) == 0
                condition_2 = sum(percents) >= 100
                if condition_1 and condition_2:
                    selectedTime = inspectedTime
                    break
            
            #Check if any time group filled the 2 conditions:
            if selectedTime:
                #selectedTime is the time group that will stay,
                #every other time will be deleted.
                relationship = org.relationships['pt2']
                sql_exp = buildSqlQuery(
                    relationship.destination.fullPath,
                    fieldsDict[42005].name,
                    selectedTime,
                    "<> timestamp"
                )
                self.deleteRelated(relationship.nickname, sql_exp)
            else:
                #No time group fills the conditions:
                #notify and continue without deleting.
                txt = 'Related table has >1 time groups, none is filling criteria for percantage summary or plant type duplications.'
                self.notifier.add(stepName, 'warning', txt)
                
        stepName = 'validateTimeDuplications - StartRepeatDominTree'
        #Import values and group by creation time:
        #[(dominTree, proportion, creationDate), ...]
        rawValues = self.getRelatedValues('pt3',[43005,43006,43008])
        groupedValues = groupByValue(rawValues, 2)
        #Get a list of all the time values and sort it:
        times = list(groupedValues.keys())
        if len(times) > 1:
            times = sorted(times, reverse=True)
            selectedTime = None
            for inspectedTime in times:
                rows = groupedValues[inspectedTime]
                #Inspect two conditions:
                #Condition 1: no duplications of dominTree
                #Condition 2: sum of proportions = 10
                dominTrees = []
                proportions = []
                for dominTree, proportion, t in rows:
                    dominTrees.append(dominTree)
                    if proportion in [None, "", "0%"]:
                        proportions.append(0)
                    else:
                        proportions.append(int(proportion.replace("%","")))
                condition_1 = len(dominTrees) - len(removeDup(dominTrees)) == 0
                condition_2 = sum(proportions) == 10
                if condition_1 and condition_2:
                    selectedTime = inspectedTime
                    break
            #Check if any time group filled the 2 conditions:
            if selectedTime:
                #selectedTime is the time group that will stay,
                #every other time will be deleted.
                relationship = org.relationships['pt3']
                sql_exp = buildSqlQuery(
                    relationship.destination.fullPath,
                    fieldsDict[43008].name,
                    selectedTime,
                    "<> timestamp"
                )
                self.deleteRelated(relationship.nickname, sql_exp)
            else:
                #No time group fills the conditions:
                #notify and continue without deleting.
                txt = 'Related table has >1 time groups, none is filling criteria for proportion summary or dominTree duplications.'
                self.notifier.add(stepName, 'warning', txt)
            del selectedTime

        return

    def c__vitalforest_desc(self):
        """
        Takes rows from related table vital forest, removes irrelevant values,
        Returns a concatenated <str> as follows:
        "defect type 1 - percent impact, defect type 2 - percent impact, ..."
        Sorted by percent value in descending order.
        """
        stepName = "vitalforest_desc"
        percentValues_sorted = [
            'אין',
            'זניח (3%-0%)',
            'מועט (10%-3%)',
            'בינוני (33%-10%)',
            'גבוה (66%-33%)',
            'גבוה מאוד (מעל 66%)'
        ]

        #a list of tuples: (defect type, percent impact)
        tupList_raw = self.getRelatedValues('pt4', [44002,44003])
        tupList = []
        # validate values
        for tup in tupList_raw:
            # 3 conditions:
            hasNull = None in tup
            # true if tup is ('אין', 'אין')
            bothEN = tup[0] == percentValues_sorted[0] and tup[1] == percentValues_sorted[0]
            invalidPercentValue = tup[1] not in percentValues_sorted
            if hasNull or bothEN:
                # don't include.
                continue
            elif invalidPercentValue:
                # notify and don't include
                txt = "invalid value (%s) in vitalforest related table." % tup[1]
                self.notifier.add(stepName, 'warning', txt)
                continue
            else:
                # validation completed
                tupList.append(tup)
        #Proceed only if tupList isn't empty:
        if tupList:
            #Sort by the index of the percent impact (magnitude):
            tupList.sort(key=lambda x: percentValues_sorted.index(x[1]), reverse = True)
            #strList = ["defect type 1 - percent impact", "defect type 2 - percent impact"]
            strList = []
            for tup in tupList:
                defecttype = tup[0]
                proportion = tup[1]
                txt = "%s - %s" % (defecttype, proportion)
                strList.append(txt)
            concat = ", ".join(strList)
            return concat
        else:
            return None
    
    def c__invasivespecies_desc(self):
        """
        Takes rows from related table invasive species, removes irrelevant values,
        Returns a concatenated <str> as follows:
        "invasive species 1 - epicenterType, invasive species 2 - epicenterType, ..."
        Sorted by epicenterType value in descending order.
        """
        stepName = "invasivespecies_desc"
        epicenterType_sorted = [
            "אין",
            "מוקד קטן",
            "מוקד בינוני",
            "מוקד גדול",
        ]

        #a list of tuples: (defect type, percent impact)
        tupList_raw = self.getRelatedValues('pt1', [41002,41003])
        tupList = []
        # validate values
        for tup in tupList_raw:
            # 3 conditions:
            hasNull = None in tup
            # true if tup is ('אין', 'אין')
            bothEN = tup[0] == epicenterType_sorted[0] and tup[1] == epicenterType_sorted[0]
            invalidPercentValue = tup[1] not in epicenterType_sorted
            if hasNull or bothEN:
                # don't include.
                continue
            elif invalidPercentValue:
                # notify and don't include
                txt = "invalid value (%s) in vitalforest related table." % tup[1]
                self.notifier.add(stepName, 'warning', txt)
                continue
            else:
                # validation completed
                tupList.append(tup)
        #Proceed only if tupList isn't empty:
        if tupList:
            #Sort by the index of the percent impact (magnitude):
            tupList.sort(key=lambda x: epicenterType_sorted.index(x[1]), reverse = True)
            #strList = ["defect type 1 - percent impact", "defect type 2 - percent impact"]
            strList = []
            for tup in tupList:
                defecttype = tup[0]
                proportion = tup[1]
                txt = "%s - %s" % (defecttype, proportion)
                strList.append(txt)
            concat = ", ".join(strList)
            return concat
        else:
            return None

    def c__planttype_desc(self):
        """
        Takes rows from related table plant type cover dist, removes irrelevant values,
        translates to shorter version, 
        Returns a concatenated <str> as follows:
        "plant type 1 - percent, plant type 2 - percent, ..."
        Every plant type text will be replaced by a short version
        according to a dictionary. 
        Not sorted by percent value.
        """
        stepName = "planttype_desc"
        planttypeShortVersions = {
            "עצים": "עצ",
            "שיחים": "שיח",
            "בני_שיח": "ב.שיח",
            "עשבוני": "עשב",
            "ללא_כיסוי": "ל.כ",
            "צומח_גדות_נחלים": "צ.ג.נ",
            "מינים_פולשים": "מ.פ"
        }

        #a list of tuples: (defect type, percent impact)
        tupList = self.getRelatedValues('pt2', [42002,42003])
        #tupList.sort(key=lambda x: x[1], reverse = True)
        #strList = ["plant type 1 - percent", "plant type 2 - percent"]
        strList = []
        for tup in tupList:
            #insert the shorter version of covtype string:
            try:
                planttype = planttypeShortVersions[tup[0]]
            except KeyError:
                #value from related table is not valid.
                #notify and continue.
                invalidValue = tup[0]
                txt = "Invalid value (%s) in related table 'planttypecoverdist'." % invalidValue
                self.notifier.add(stepName, 'warning', txt)
                #continue - the value will not be included.
                continue
            proportion = tup[1]
            txt = "%s - %s" % (planttype, proportion)
            strList.append(txt)
        
        if strList:
            concat = ", ".join(strList)
            return concat
        else:
            return None

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
        try:
            vegForm_split = self.vegForm.split(',')

            #remove strings from vegForm_split list:
            valuesToRemove = ['', ' ']
            for valueToRemove in valuesToRemove:
                while valueToRemove in vegForm_split: 
                    vegForm_split.remove(valueToRemove)

            vegForm_possibleValues = forestVegFormCoordinator.inputOptions
            #Check every splitvalue is one of the available options:
            for splitVal in vegForm_split:
                if splitVal not in vegForm_possibleValues:
                    txt = 'Point %s: %s. Veg form value (%s) is not one of the following: %s.'\
                    % (self.parent.FC.oidFieldName, self.parent.id, splitVal, vegForm_possibleValues)
                    self.parent.notifier.add(stepName, 'warning', txt)

            #Proceed according to lenght of list:
            if len(vegForm_split) == 0:
                self.vegForm = None
                self.vegForm_translated = None
                self.vegForms = []
            elif len(vegForm_split) == 1:
                #(practicly, same as self.vegForm)
                self.vegForm = vegForm_split[0]
                self.vegForm_translated = translate(self.vegForm, subForestVegForm_translation)
                self.vegForms = [self.vegForm]
            elif len(vegForm_split) == 2:
                #Edit the vegform that was previously raw:
                self.vegForm = forestVegFormCoordinator.solve(vegForm_split)
                self.vegForm_translated = translate(self.vegForm, subForestVegForm_translation)
                self.vegForms = vegForm_split
            elif len(vegForm_split) > 2:
                #Notify
                vegForm_fieldObj = fieldsDict[fieldsList[0]]
                txt = 'Veg form field [%s,%s] has more than 2 values: %s. Process continued with the first two vegforms only. Removing other values from table.' \
                    % (vegForm_fieldObj.name, vegForm_fieldObj.alias, vegForm_split)
                self.parent.notifier.add(stepName, 'warning', txt)
                #Solve matrix for the first two veg forms:
                vegForm_split_trimmed = vegForm_split[:2]
                self.vegForm = forestVegFormCoordinator.solve(vegForm_split_trimmed)
                self.vegForm_translated = translate(self.vegForm, subForestVegForm_translation)
                self.vegForms = vegForm_split_trimmed

                #Update row values from "A,B,C" to "A,B" (leave the first two).
                vegForm_joined = ','.join(vegForm_split_trimmed)
                rawValues[0] = vegForm_joined
                self.parent.writeSelf(fieldsList[0], vegForm_joined)

        except AttributeError:
            #AttributeError is when 'NoneType' object has no attribute 'split'
            # self.vegForm
            self.vegForm = None
            self.vegForm_translated = None
            self.vegForms = []
        else:
            #Validates according to self.vegForm:
            if self.vegForm:
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
        stepName = 'subforest layer creation'

        #Obtain values:
        self.presenceConifer = self.parent.getSelfValue(40055)
        self.presenceConiferType = self.parent.getSelfValue(40056)
        self.presenceBroadLeaf = self.parent.getSelfValue(40057)
        self.presenceBroadLeafType = self.parent.getSelfValue(40058)

        #subForestCover is a dict of {type: percent <int> or <None>}
        self.subForestCover = self.subForestCover()

        #Calculate variables for logic:
        self.isConiferForest = self.coniferForest()
        self.isBroadleafForest = self.broadleafForest()
        self.isRiverbank = self.hasRiverbank()
        self.hasShrubOrGrassCover = self.hasShrubOrGrass()

        #Check subforest layer validity:
        #   Check if at least one of 3 conditions matches.
        #   תנאי -או.
        booleanArrayForValidation = [
            #האם השכבה מקיימת תנאים של התחדשות מחטני או רחבי עלים
            self.isConiferForest or self.isBroadleafForest,
            #האם השכבה מקיימת תנאים של צומח גדות נחלים
            self.isRiverbank,
            #האם השכבה מקיימת תנאים של צומח מתוך 3 אופציות לפחות 10
            self.hasShrubOrGrassCover
        ]
        self.isValid = True in booleanArrayForValidation

    def subForestCover(self):
        """
        A helper method for organizing data of sub forest cover
        from related table.
        Returns a dict of {type: percent <int>}.
        Pay attention: for performence, this method uses a 
        VARIATION of the global function getValue().
        """
        outdict = {k:None for k in subCoverType_domain}
        """
        #this is what the above does:
        outdict = {
            "שיחים": None,
            "בני_שיח": None,
            "עשבוני": None,
            "עצים": None,
            "ללא_כיסוי": None
        }
        """
        relatedValues = self.parent.getRelatedValues('pt2',[42002, 42003])
        for subPlantType, subPlantPercent in relatedValues:
            #Handle values of subPlantPercent and convert to integer.
            if subPlantPercent in [None, "", "0%"]:
                subPlantPercent = 0
            else:
                subPlantPercent = int(subPlantPercent.replace("%",""))

            #Assign values into outdict.
            if subPlantType in outdict.keys():
                if outdict[subPlantType] == None:
                    #e.g: if it is the first time a value is given.
                    #turn it to zero in order to add.
                    outdict[subPlantType] = 0
                outdict[subPlantType] += subPlantPercent
            elif type(subPlantPercent) is int:
                #Any other category subPlantType including None
                #Then just add it to "ללא_כיסוי":
                if outdict["ללא_כיסוי"] == None:
                    #e.g: if it is the first time a value is given.
                    #turn it to zero in order to add.
                    outdict["ללא_כיסוי"] = 0
                outdict["ללא_כיסוי"] += subPlantPercent

        #correction from Achiad's e-mail in Aug 14th, 2022:
        #add cover of TREES → to → shrub (שיחים)
        if outdict[subCoverType_domain[3]]:
            #עצים value is not 0 or None.
            if outdict[subCoverType_domain[0]] == None:
                outdict[subCoverType_domain[0]] = outdict[subCoverType_domain[3]] # +0
            elif type(outdict[subCoverType_domain[0]]) is int:
                outdict[subCoverType_domain[0]] += outdict[subCoverType_domain[3]]
        return outdict

    def coniferForest(self):
        #Returns True if sub forest conifer forest meets criteria.
        #Convert presenceConifer to index based on domain,
        #obtain threshold based on presenceConiferType.
        index = presenceConifer_domain.index(self.presenceConifer)
        if self.presenceConiferType in presenceConifer_threshold.keys():
            threshold = presenceConifer_threshold[self.presenceConiferType]
            return index >= threshold
        else:
            return False

    def broadleafForest(self):
        #Returns True if sub forest broadleaf forest meets criteria.
        #Convert presenceBroadLeaf to index based on domain,
        #obtain threshold based on presenceBroadLeafType.
        index = presenceBroadleaf_domain.index(self.presenceBroadLeaf)
        if self.presenceBroadLeafType in presenceBroadleaf_threshold.keys():
            threshold = presenceBroadleaf_threshold[self.presenceBroadLeafType]
            return index >= threshold
        else:
            return False

    def hasRiverbank(self):
        #Returns true if at least a single plant mentioned in fields
        #"subTreeSp_names", "subShrubSp_names" is a riverside plant (from a list).
        #1.9.2022: riverbankSpecies is empty, costumer requested to skip this 
        #          step and return False
        return False
        """
        subTreeSp_names = self.subTreeSp_names
        subShrubSp_names = self.subShrubSp_names
        #Correct values: None to "" string:
        if subTreeSp_names is None:
            subTreeSp_names = ""
        if subShrubSp_names is None:
            subShrubSp_names = ""
        subSpecies = subTreeSp_names.split(",") + subShrubSp_names.split(",")
        for sp in subSpecies:
            if sp in riverbankSpecies:
                return True
        return False
        """

    def hasShrubOrGrass(self):
        #Returns True if שיחים / בני שיח / עשבוניים cover is >= 10.
        #TRY/EXCEPT statement for creating the variable if doesn't exist.
        try:
            self.subForestCover
        except AttributeError:
            #it doesn't exist, so create it.
            self.subForestCover = self.subForestCover()
        for coverType in subCoverType_domain[:3]:
            #Check if a value was inserted:
            if self.subForestCover[coverType] is None: continue
            #Check values for the first THREE types:
            #Return True if any of the values is >= 10.
            if self.subForestCover[coverType] >= 10:
                return True
        return False

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

    def assignLayer(self, layer, isPrimary):
        self.assigned = True
        self.isPrimary = isPrimary
        self.layerNum = layer.layerNum
        if self.layerNum in [4,3,2]:
            self.isForestLayer = True
        self.layerShortText = layerToShortText[self.layerNum]
        self.layerLongText = layerToLongText[self.layerNum]
        self.layerLongText_m = layerToLongText_m[self.layerNum]
        
        self.layerCover = layer.layerCover
        self.layerCover_num = layerCover_table1[self.layerCover][0]
        self.layerCover_avg = layerCover_table1[self.layerCover][1]

        self.vegForm = layer.vegForm
        self.vegForm_translated = layer.vegForm_translated

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

    def __repr__(self):
        #return self.asText()
        validity = {True:'valid',False:'invalid'}[self.isValid]
        return "LayerResult object: %s [%s]." % (self.layerDesc, validity)

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


#PROCESS
arcpy.env.overwriteOutput = True
org = Organizer(
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

#Create species hierarchy:
root = Node()
arrayToTree(speciesHierarchy_jsonObject, root)
#create speciesDict based on root node:
speciesDict = createSpeciesDict(root, speciesHierarchy_path)

#Validate stuff:
#### Process section 0: ####
# Check fields exist and notify if not.
# Create new fields by sequence.

# 0.1: Change the field name of field 40000 - points object id
# (it won't always be "objectid"). Instead, look for the object id
# and assign it to code 40000.
fieldsDict[40000].name = getOidFieldName(org.sekerpoints.name)

# (0.2 validates stands FC, hence is irrelevant for this tool).

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
del smallFieldObj


#D)PATCH 7/8/24
#  edit 5/11/24: repeat for both 'צומח גדות נחל' and 'צמחים פולשים'
table = org.relationships['pt2'].destination
domainOI = 'cvd_PlantType'
#[(codedValue_from, codedValue_to, codedValue_description)]
codedValues_substitutes = [
    (
        'צומח_גדות_נחל',
        'צומח_גדות_נחלים',
        'צומח גדות נחלים'
    ),
    (
        'צמחים פולשים',
        'מינים_פולשים',
        'מינים פולשים'
    )
]
fieldName = fieldsDict[42002].name

#### PATCH START ####
for codedValue_from, codedValue_to, codedValue_description in codedValues_substitutes:
    #  D.1)EDIT DOMAIN "cvd_PlantType"
    if domainOI.lower() in [n.lower() for n in table.wsDomains]:
        #GDB has the domain of this name. Inspect its coded values.
        domainOI_exactName = [n for n in table.wsDomains if n.lower() == domainOI.lower()][0]
        codedValues = listCodedValues(table.workspace, domainOI_exactName)
        if codedValue_from in codedValues:
            txt = 'In domain "%s" deleting coded value "%s".' % (domainOI_exactName, codedValue_from)
            arcpy.AddMessage(txt)
            #Delete bad coded value
            arcpy.management.DeleteCodedValueFromDomain(
                table.workspace,
                domainOI_exactName,
                codedValue_from
                )
        if codedValue_to not in codedValues:
            txt = 'In domain "%s" adding coded value "%s".' % (domainOI_exactName, codedValue_to)
            arcpy.AddMessage(txt)
            #Create it
            arcpy.management.AddCodedValueToDomain(
                table.workspace,
                domainOI_exactName,
                codedValue_to,
                codedValue_description
                )
        del domainOI_exactName, codedValues
    else:
        #GDB does not have the domain of this name. Import it from origin.gdb.
        txt = 'Importing domain "%s".' % domainOI
        arcpy.AddMessage(txt)
        importDomain(domainOI, origin_GDB, table.workspace)

    #  D.2)convert vlaues "צומח_גדות_נחל" >to> "צומח_גדות_נחלים"
    #build sql query:
    fieldName_delimited = arcpy.AddFieldDelimiters(table.workspace, fieldName)
    sql_exp = """{0} = '{1}'""".format(fieldName_delimited, codedValue_from)
    #query rows with bad values:
    uc = arcpy.UpdateCursor(table.fullPath, where_clause=sql_exp)
    for r in uc:
        r.setValue(fieldName, codedValue_to)
        uc.updateRow(r)
        txt = 'Editing table "%s" (id:%s): replacing "%s" with "%s".' % (table.name, r.getValue('objectid'), codedValue_from, codedValue_to)
        arcpy.AddMessage(txt)
    del uc
del table, fieldName, codedValue_from, codedValue_to, codedValue_description, fieldName_delimited, sql_exp, domainOI

#### PATCH END ####


#### Process section 1: ####
# Add blank fields to sekerpoints FC by sequence.
# Or move fields with their values by sequence.
if addFields:
    #Find the relevant fields, based on 'toAdd' attribute:
    fieldsToHandle = set()
    for sf in fieldsDict.values():
        #Not all values has these attributes.
        if hasattr(sf,'toAdd') and hasattr(sf,'code'):
            #Checks: 1)need to add, and 2)belongs to 'sekerpoints':
            if sf.toAdd and str(sf.code)[:2] == '40':
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
            globalID_fieldObj = fieldsDict[40002]
            moveFieldToEnd(org.sekerpoints, smallFieldObj, globalID_fieldObj)
        elif smallFieldObj.toAdd == 'blank':
            createBlankField(org.sekerpoints, smallFieldObj)

        arcpy.SetProgressorPosition()
        counter += 1
    del counter, tempMessage
    arcpy.ResetProgressor()

#### Process section 2: ####
# Create Matrices: 
# Must run after creation of fields.
forestVegFormCoordinator = MatrixCoordinator(forestVegFormExcel)
standVegFormCoordinator = MatrixCoordinator(standVegFormExcel)
speciesCompositionCoordinator = MatrixCoordinator(speciesCompositionExcel)
relativeDensityKeyCoordinator = Matrix3DCoordinator(relativeDensityKeyExcel)
totalCoverageCoordinator = TotalCoverageMatrixCoordinator(totalCoverageExcel, org.sekerpoints.shapeType)

#### Process section 3: ####
# Go through each sekerpoint:

#Notify in UI about process start:
message = 'Calculating...'
featureCount = getFeatureCount(org.sekerpoints.name)
arcpy.SetProgressor("step",message,0,featureCount,1)
arcpy.AddMessage(message)
counter = 1

#@
sekerpoints_uc = arcpy.UpdateCursor(
    org.sekerpoints.name,
    #where_clause = 'objectid > 144', #for debug!!!
    sort_fields = "%s A" % org.sekerpoints.oidFieldName
    )
#Main iteration:
for sekerpoint_r in sekerpoints_uc:
    tempMessage = 'Calculating... (row: %s of %s feafures)' % (counter, featureCount)
    arcpy.SetProgressorLabel(tempMessage)

    sekerpointObj = SekerPoint(sekerpoint_r, org.sekerpoints)
    sekerpoints_uc.updateRow(sekerpointObj.row)

    arcpy.SetProgressorPosition()
    counter += 1
del sekerpoints_uc

#Delete fields that don't appear in fields.xlsx:
arcpy.ResetProgressor()
message = 'Deleting fields'
arcpy.SetProgressor("default",message)
arcpy.AddMessage(message)

feature = org.sekerpoints.fullPath
listfields = arcpy.ListFields(feature)
#select the fields that start with 40 = relevant for
fieldsDict_40 = [v.name.lower() for k,v in fieldsDict.items() if str(k)[:2]=="40"]

for field in listfields:
    name = field.name
    if name.lower() not in fieldsDict_40:
        arcpy.ResetProgressor()
        message = 'Deleting field - %s' % name
        arcpy.SetProgressor("default",message)
        arcpy.AddMessage(message)
        
        arcpy.management.DeleteField(feature, field.name)
arcpy.ResetProgressor()

print('done')