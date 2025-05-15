# -*- coding: utf-8 -*-
import os
import arcpy
import json
import math
from collections import Counter
import numpy as np

#TOOL PARAMETERS
debug_mode = False
if debug_mode:
    #debug parameters
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\QA\8.5.2025\smy_Turan2024_BKP_25082024.gdb'
    input_stands = os.path.join(input_workspace, 'stands_1402_fnl')
    input_unitelines = os.path.join(input_workspace, 'הערותקוויותלדיוןשני__Project')
    #input_configurationFolder = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\Github - Deshe\Deshe\DesheTools\configuration'
    input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')
    input_beitGidul = "ים-תיכוני"
else:
    input_stands = arcpy.GetParameter(0)
    #Take all the features, even if layar has selection.
    input_stands = arcpy.Describe(input_stands).catalogPath
    
    input_unitelines = arcpy.GetParameter(1)
    #Take all the features, even if layar has selection.
    input_unitelines = arcpy.Describe(input_unitelines).catalogPath

    input_configurationFolder = arcpy.GetParameterAsText(2)
    #input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')

    input_beitGidul = arcpy.GetParameterAsText(3)


#VARIABLES
fieldsExcel = os.path.join(input_configurationFolder, 'fields.xlsx')
fieldsExcel_sheet = 'unite stands'
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

unitelines_stands_relationship = {
    'nickname': 'ls',
    'name': "_".join([os.path.basename(input_unitelines), os.path.basename(input_stands)]),
    'originKey_code': 60002,
    'destinationKey_code': 50024
}

stands_tables_relationships = {
    #'nickname': ('name of relationship class', field codes prefix <int>),
    'st1': ("_".join([os.path.basename(input_stands)]*2) + '_InvasiveSpecies', 51),
    'st2': ("_".join([os.path.basename(input_stands)]*2) + '_PlantTypeCoverDistribut', 52),
    'st3': ("_".join([os.path.basename(input_stands)]*2) + '_StartRepeatDominTree', 53),
    'st4': ("_".join([os.path.basename(input_stands)]*2) + '_VitalForest', 54),
}

beitgidulList = [
    "ים-תיכוני",
    "ים-תיכוני יבש",
    "צחיח-למחצה"
]

#Fields to be added to each related table
#the first one is ALWAYS used for linkage in relationship class!
#the order of the other codes matters as well.
#[stand_ID, standAddress, FOR_NO, HELKA, STAND_NO]
stands_relatedTables_globalFieldCodes = [59001,59002,59003,59004,59005]

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

def removeDup(array):
    #returns a list w/o duplications.
    return list(set(array))

def get_spatialRelation(shapeList):
    """
    Takes a list of two geometries and returns their spatial relationship [<str>, ...].
    """
    geom1 = shapeList[0]
    geom2 = shapeList[1]
    outputList = []

    # Check spatial relationships
    if geom1.disjoint(geom2):
        outputList.append("Disjoint")
    if geom1.touches(geom2):
        outputList.append("Touches")
    if geom1.contains(geom2):
        outputList.append("Contains")
    if geom1.overlaps(geom2):
        outputList.append("Overlaps")
    if geom1.within(geom2):
        outputList.append("Within")
    if geom1.crosses(geom2):
        outputList.append("Crosses")
    
    return outputList

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

def findNodesAbove(node,val,array):
    #Appends to array every node that its value is above val.
    if node.value>val:
        array.append(node)
    for child in node.children:
        findNodesAbove(child,val,array)

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

def getFeatureCount(feature):
    return int(arcpy.management.GetCount(feature)[0])

def getOidFieldName(fc):
    #returns the Objectid field of a fc.
    fc_desc = arcpy.Describe(fc)
    oidFieldName = fc_desc.oidFieldName
    del fc_desc
    return oidFieldName

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

def normal_round(n):
    """
    This is a round function that rounds .5 up.
    [The built-in round() doesn't do it properly].
    """
    if n - math.floor(n) < 0.5:
        return math.floor(n)
    return math.ceil(n)

def roundToNearestBase(numbers, base):
    """
    Rounds an array of numbers to their nearest multiple of X (base),
    after doing so, it ensures the sum remains their original sum,
    if not, it will add or substract X from the numbers with
    the largest difference between original and rounded value.
    """
    target_sum = sum(numbers)
    rounded_numbers = np.round(np.array(numbers) / base) * base
    difference = target_sum - np.sum(rounded_numbers)
        
    # Ensure values that were originally 0 remain unchanged
    rounded_numbers = np.where(np.array(numbers) == 0, 0, rounded_numbers)

    difference = target_sum - np.sum(rounded_numbers)

    if difference != 0:
        indices = np.argsort(np.abs(rounded_numbers - numbers))
        for i in range(int(abs(difference) / base)):
            if rounded_numbers[indices[i]] != 0:
                # Skip if the value is 0
                rounded_numbers[indices[i]] += np.sign(difference) * base
    rounded_numbers = [int(n) for n in rounded_numbers]
    return rounded_numbers

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

def splitAndRemoveSpacesFromEnds(inputString, splitChar):
    """
    split a string using a character
    if any split value starts or ends with spaces
    they will be removed.
    returns a list of split values.
    """
    results = []
    for splitVal in inputString.split(splitChar):
        if len(splitVal) == 0: continue
        while splitVal.endswith(' '):
            splitVal = splitVal[:len(splitVal)-1]
        if len(splitVal) == 0: continue
        while splitVal.startswith(' '):
            splitVal = splitVal[1:]
        if len(splitVal) == 0: continue
        results.append(splitVal)
    return results

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

def isOrIsChildOf_code(inputNode, inputCode):
    """
    Returns True if the input node, or any of its parents,
    has the inputCode as their codedValue (a node's attribute). 
    """
    nodeCode = inputNode.codedValue
    if nodeCode == inputCode:
        return True
    elif inputNode.parent:
        return isOrIsChildOf_code(inputNode.parent, inputCode)
    else:
        return False

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
    def __init__(self, stands, unitelines, standsRelationships):
        self.stands = FeatureClass(stands)
        self.unitelines = FeatureClass(unitelines)
        #Coordinate system of both FCs must be the same.
        self.checkSR([self.stands, self.unitelines])
        if self.stands.workspace != self.unitelines.workspace:
            arcpy.AddError('Stands and seker points are not in the same workspace.')
        arcpy.env.workspace = self.stands.workspace
        self.relationships = {
            #'nickname': RelationshipClass,
        }
        #Create and bind RelationshipClasses existing relationships between stand
        #and its related TABLES.
        for nickname, relTup in standsRelationships.items():
            #relTup = ('name of relationship class', field codes prefix <int>)
            relName = relTup[0]
            fieldCodesPrefix = relTup[1]
            #relationships <dict>: 'nickname': 'name of relationship class'.
            self.relationships[nickname] = RelationshipClass(relName, nickname, self.stands)
            #a patch to relationship's destination FC:
            #was made for verification of field existance.
            self.relationships[nickname].destination.fieldCodesPrefix = fieldCodesPrefix
        #Create and bind RelationshipClasses existing relationships between stand
        #and its related POINTS.
        #Find the relationship between current stands and points:
        relDesc = self.getRelationshipToSekerpoints()
        relName = relDesc.name
        nickname = 'sp'
        self.relationships[nickname] = RelationshipClass(relName, nickname, self.stands)
        


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

    def getRelationshipToSekerpoints(self):
        """
        Finds the relationship between current stands and points.
        Returns arcpy.Describe object of the relationship
        """
        for relationshipName in self.stands.desc.relationshipClassNames:
            relDesc = arcpy.Describe(relationshipName)
            destDesc = arcpy.Describe(relDesc.destinationClassNames[0])
            if destDesc.datasetType == 'FeatureClass':
                if destDesc.shapeType == 'Point':
                    return relDesc
        # If the code got here it means the stands are not related to any
        # point featureclass in its workspace, code should be stopped.
        txt = "Stands feature class is not related to any point feature class in its workspace."
        arcpy.AddError(txt)
        self.__exit() # this method is non-existent, meant to crash.
        return None


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
        # Solution: check if destination name == unitelines name:
        if 'org' in globals():
            if org.unitelines.name == self.desc.destinationClassNames[0]:
                self.destination = org.unitelines
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
    A layer that is built based on calculated fields of product polygon,
    and holds their attributes:
    - layer
    - cover
    - veg form
    - species #@suspended
    Queries the sekerpoint's attributes a desired layer.
    Input parameters:
    - parent - a ProductPolygon object (parent).
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
            4: [50046, 50047, 50048],
            3: [50050, 50051, 50052],
            2: [50054, 50055, 50056],
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
        #@ suspended
        validationConditionsMet += 1
        """
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
        """
        
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
                    txt = 'Veg form value (%s) is invalid.' % splitVal
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
    process of c__logiclayers()). In that case, the enhance
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
        self.presenceConifer = self.parent.getSelfValue(50063)
        self.presenceConiferType = self.parent.getSelfValue(50064)
        self.presenceBroadLeaf = self.parent.getSelfValue(50065)
        self.presenceBroadLeafType = self.parent.getSelfValue(50066)

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
        relatedValues = self.parent.getRelatedValues('st2',[52001, 52002])
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
                'domainValues': listCodedValues(org.stands.workspace, fieldsDict[40022].domain)
            },
            {
                'name': 'generalDensity',
                'source': fieldsDict[50042].name,
                'domain': fieldsDict[50042].domain,
                'domainValues': listCodedValues(org.stands.workspace, fieldsDict[50042].domain)
            },
            {
                'name': 'relativeDensity',
                'source': fieldsDict[50044].name,
                'domain': fieldsDict[50044].domain,
                'domainValues': listCodedValues(org.stands.workspace, fieldsDict[50044].domain)
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
    #Basic object for UniteLine and StandPolygon.
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

class UniteLine(FcRow):
    #Each unite line in unitelines gets an object.
    def __init__(self, row, unitelinesFC):
        FcRow.__init__(self, row, unitelinesFC)
        arcpy.AddMessage('Started calculating: uniteLine %s = %s'% (self.FC.oidFieldName, self.id))
        self.notifier = Notifier(self, 60005)

        self.stands = self.getStands(org.stands)
        self.joint_isValid = self.validateJoint() 

        if self.joint_isValid:
            # write joint status:
            self.writeSelf(60003, 'תקין')
            # sort stands: larger area first.
            self.stands.sort(key=lambda x: x.area, reverse = True)
            
            # Write a new empty row in stands
            prod_ic = arcpy.da.InsertCursor(org.stands.fullPath,["SHAPE"])
            # Obtain new stand's object ID
            productPolygon_ID = prod_ic.insertRow([None])
            del prod_ic

            # Create a Product Polygon (new stand) object
            sql_expression = f"{org.stands.oidFieldName} = {productPolygon_ID}"
            prod_uc = arcpy.UpdateCursor(org.stands.fullPath, sql_expression)
            prod_r = prod_uc.next()
            self.productPolygon = PoductPolygon(self, prod_r, org.stands)

            self.productPolygon.calculateAndWrite()
            prod_uc.updateRow(self.productPolygon.row)
            del prod_uc
            
            calculatedJoints.append(self)
        
        else:
            # write joint status:
            self.writeSelf(60003, 'לא תקין')
        
        self.notifier.write()

    def getStands(self, standsFC):
        """
        Finds stands that contain this unite line start-, and end-points.
        Returns a list of StandPolygons.
        """
        stands = []
        uniteLine_shape = self.getSelfValue(60001)
        unitePoints = [uniteLine_shape.firstPoint, uniteLine_shape.lastPoint]
        unitePoints_shapes = [arcpy.PointGeometry(p, uniteLine_shape.spatialReference) for p in unitePoints]
        
        stands_sc = arcpy.SearchCursor(standsFC.fullPath)
        for stands_r in stands_sc:
            stand_shape = stands_r.getValue("SHAPE")
            if stand_shape is None: 
                continue
            if unitePoints_shapes:
                for unitePoint_shape in unitePoints_shapes:
                    # "within" is the requested spatial relationship between point and polygon
                    if unitePoint_shape.within(stand_shape):
                        # Create a new StandPolygon object
                        stand = StandPolygon(self, stands_r, org.stands)
                        stands.append(stand)
                        unitePoints_shapes.remove(unitePoint_shape)
            else:
                # Both start and end-points were found.
                break
        del stands_sc
        return stands

    def validateJoint(self):
        """
        Runs a set of tests to validate the joint between two stands:
        1 - Two stands
        2 - Same Helka
        3 - Stands has not been used by other joint
        4 - Stands touch each other. for now - does not disqualify joint.
        Returns Boolean.
        """
        stepName = 'validateJoint'
        # A default result:
        result = True

        # Conditions are numbered:
        # 1 - the endpoints of the line are within 2 stands:
        if len(self.stands) != 2:
            txt = "line does not start or end within 2 stands."
            self.notifier.add(stepName, 'warning', txt)
            # The next conditions require 2 polygons,
            # so 'return' (break) is appropriate.
            return False
        
        # 2 - stands belong to the same 'HELKA':
        helka_numbers = [stand.getSelfData(50003) for stand in self.stands]
        if len(removeDup(helka_numbers)) != 1:
            txt = "polygons are not in the same helka."
            self.notifier.add(stepName, 'warning', txt)
            result = False

        # 3 - stands objectid has not been used for other union:
        for stand in self.stands:
            stand_id = stand.id
            for joint in calculatedJoints:
                calculated_standIDs = [s.id for s in joint.stands]
                if stand_id in calculated_standIDs:
                    # stand was already been used for another unite line:
                    txt = "stand (id - %s) was used for another unite line (line id - %s)." % (stand_id, joint.id)
                    self.notifier.add(stepName, 'warning', txt)
                    result = False

        # 4 - stands geometry relation is TOUCHING
        stand_shapes = [s.getSelfData(50001) for s in self.stands]
        spatial_relation = get_spatialRelation(stand_shapes)
        spatial_relation_txt = ','.join(spatial_relation)
        self.writeSelf(60004, spatial_relation_txt)
        if "Touches" not in spatial_relation:
            txt = "polygons are not touching. Instead they are: %s." % spatial_relation
            self.notifier.add(stepName, 'warning', txt)
            #for now this condition DOES NOT DISQUALITY a joint.
            #result = False
        
        return result
    
class StandPolygon(FcRow):
    def __init__(self, parentFcRow, row, sekerpointsFC):
        FcRow.__init__(self, row, sekerpointsFC)
        self.parent = parentFcRow
        self.notifier = self.parent.notifier

        self.selfData = {}
        self.relatedData = {}
        self.acquireData()

        self.area = self.getSelfData(50001).area

    def __repr__(self):
        return "StandPolygon object, id = %s" % self.id

    def acquireData(self):
        """
        Used this method to query all the data from this stand polygon
        and its related tables.
        """
        # Self values - from the stand polygon itself
        fieldCodes_self = [
            50001,
            50002, 50003, 50004,
            50027, 50081, 50042, 50043,
            50046, 50047, 50048, 50049, 
            50050, 50051, 50052, 50053, 
            50054, 50055, 50056, 50057, 
            50045,
            50088,
            50089,
            50063, 50064, 50065, 50066,
            50067, 50068, 50069, 50070, 50071,
            50075, 50076, 50077, 50078,
            50072,
            50103, 50104, 50105, 50106,
            50041,
            50059, 50060, 50061, 50062,
        ]
        for fieldCode in fieldCodes_self:
            # data structure of selfData:
            # {fieldCode: value, ...}
            self.selfData[fieldCode] = self.getSelfValue(fieldCode)
        
        # Related values - from the stand's related tables
        fieldCodes_related = {
            'st1': [51001, 51002],
            'st2': [52001, 52002],
            'st3': [53001, 53002],
            'st4': [54001, 54002],
            'sp': [40013, 40020, 40024, 40025, 40034, 40035, 40044, 40045 ,40114, 40119]#@, 40115]
        }
        for nickname, fieldCodes in fieldCodes_related.items():
            # data structure of relatedData:
            # {nickname: {fieldCode_A: (value_from_row_0, value_from_row_1, ...),
            #             fieldCode_B: (value_from_row_0, value_from_row_1, ...)},}
            self.relatedData[nickname] = {}
            queriedData = self.getRelatedValues(nickname, fieldCodes)
            for i, fieldCode in enumerate(fieldCodes):
                tup = tuple([queryTuple[i] for queryTuple in queriedData])
                self.relatedData[nickname][fieldCode] = tup
        
        return
    
    def getSelfData(self, fieldCode):
        """
        Takes a field code of stands,
        checks if this data exists in self.selfData:
        if it does: return it,
        if it does not: nofity and return None.
        """
        stepName = 'getSelfData'
        try:
            return self.selfData[fieldCode]
        except KeyError:
            txt = "StandPolygon object does not have data of field code - %s. \
Make sure it appears in 'acquireData' method" % fieldCode
            self.notifier.add(stepName, 'error', txt)
            return None

    def getRelatedData(self, nickname, fieldCodes):
        """
        Takes a relationship nickname and 
        field code or a list of field codes,
        checks if the data exists in self.relatedData:
        if it does: return it,
        if it does not: nofity and return None.
        Parameters:
        - nickname <str>: nickname of relationship,
        - fieldCodes <int>/<list>: field code / codes.
        Returns:
        # a - first field, b - second field
        # 1 - of row 1, ...
        - [
        (Val_a1, Val_b1),
        (Val_a2, Val_b2), ...
        ]
        """
        stepName = 'getRelatedData'
        if type(fieldCodes) is not list:
            fieldCodes = [fieldCodes]
        
        try:
            data = self.relatedData[nickname]
            result = []
            n_rows = len(data[fieldCodes[0]])
            for row_index in range(n_rows):
                tup = tuple([data[fieldC][row_index] for fieldC in fieldCodes])
                result.append(tup)
            return result
        except:
            txt = "error during getRelatedData method, check code."
            self.notifier.add(stepName, 'error', txt)
            return None

class PoductPolygon(FcRow):
    def __init__(self, parentFcRow, row, sekerpointsFC):
        FcRow.__init__(self, row, sekerpointsFC)
        stepName = 'polygonInitiation'
        self.parent = parentFcRow
        self.notifier = self.parent.notifier
        self.stands = self.parent.stands

        # Area proportions of source stands
        sumArea = sum([s.area for s in self.stands])
        # The first stand is always larger
        self.stands[0].areaProportion = self.stands[0].area/sumArea
        self.stands[1].areaProportion = self.stands[1].area/sumArea

        self.areaDominance = self.stands[0].areaProportion >= 0.8
        # Notify area dominance
        if self.areaDominance:
            txt = "area proportion >= 80%."
            self.notifier.add(stepName, 'message', txt)

        # Set polygon's shape
        self.shape = self.constructGeometry()
        self.writeSelf(50001, self.shape)

        # Relate polygon with the unite line
        self.relate()

        # Create stamp object
        self.stamp = self.getStamp()

    def __repr__(self):
        return "ProductPolygon object, id = %s" % self.id
    
    def constructGeometry(self):
        """
        Constructs the polygon geometry by union of two stands.
        """
        uniteL = self.parent
        polygons = [stand.getSelfData(50001) for stand in uniteL.stands]
        unionPolygon = polygons[0].union(polygons[1])
        return unionPolygon

    def relate(self):
        """
        Relate this polygon with the unite line.
        """
        relationship = org.relationships['ls']
        stand_ID = self.row.getValue(relationship.foreignKey_fieldName)
        self.parent.row.setValue(relationship.originKey_fieldName, stand_ID)
        return

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

        #the first (larger) stand will be used
        stand = self.parent.stands[0]
        
        for_no = stand.getSelfData(query_fieldCodes[0])
        helka = stand.getSelfData(query_fieldCodes[1])
        stand_no = stand.getSelfData(query_fieldCodes[2])

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

    def getMatrix_self(self, fieldCode):
        """
        Takes a field code <int> or codes [<int>,] and returns the next matrix:
        [
            (area proportion <float>, data*), #stand 0
            (area proportion <float>, data*), #stand 1
        ]
        *data - according to type of fieldCode:
        fieldCode <int> → return a single value,
        fieldCode [<int>,] → return a a list of values.
        """
        inputIslist = type(fieldCode) is list
        matrix = []
        for stand in self.stands:
            if inputIslist:
                data = []
                for fCode in fieldCode:
                    data.append(stand.getSelfData(fCode))
            else:
                data = stand.getSelfData(fieldCode)
            tup = (
                stand.areaProportion,
                data
            )
            matrix.append(tup)
        return matrix

    def getMatrix_related(self, nickname, fieldCodes):
        """
        Takes relationship nickname and field code(s)
        and returns the next matrix:
        [
            (area proportion <float>, data), #stand 0
            (area proportion <float>, data), #stand 1
        ]
        """
        matrix = []
        for stand in self.stands:
            tup = (
                stand.areaProportion,
                stand.getRelatedData(nickname, fieldCodes)
            )
            matrix.append(tup)
        return matrix
    
    def setLayers(self):
        """
        Creating layer objects (forest and sub-forest) based on calculations
        that were made previously in the code.
        A helper function to run inside c__logiclayers method.
        Background: in previous scripts the layer object were set during
        the code, but this time it is not necessary.
        """
        layers = {
            'tmira': ForestLayer(self, 4),
            'high': ForestLayer(self, 3),
            'mid': ForestLayer(self, 2),
            'sub': SubForestLayer(self)
        }
        return layers

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
        """
        Special notice for Unite Stands:
        1) At this point, there are Two active rows: 
            UniteLine (self.parent) & ProductPolygon(self)
            the later is a row of the new stand, not the existing stands being combined.
        2) All data from the source stands must be queried in advance, 
            in self.stands.__init__ method. because their rows are inactive now.
        """

        # SELF FIELDS:
        # STAMP FIELDS:
        self.writeSelf(
            [50002, 50003, 50004],
            [tup[1] for tup in self.stamp[:3]]
        )
        
        self.v__generaldensity = self.c__density('general')
        self.v__standdensity = self.c__density('stand')
        self.writeSelf([50042, 50043], [self.v__generaldensity, self.v__standdensity])

        self.v__actualagegroup = self.c__actualagegroup()
        self.writeSelf(50045, self.v__actualagegroup)

        self.v__relativedensity = self.c__relativedensity(
            self.v__actualagegroup,
            self.v__generaldensity,
            input_beitGidul
        )
        self.writeSelf(50044, self.v__relativedensity)

        self.v__start_year = self.c__start_year()
        self.writeSelf(50027, self.v__start_year)
        self.v__last_year = self.c__last_year()
        self.writeSelf(50081, self.v__last_year)

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

        self.v__totalcoverage = self.c__totalcoverage()
        self.writeSelf(50088, self.v__totalcoverage)

        self.v__presenceconifer = self.c__presence('conifer')
        self.v__presenceconifertype = self.c__presencetype(50064)
        self.isConiferForest = self.coniferForest(
            self.v__presenceconifer, 
            self.v__presenceconifertype
        )
        self.v__presencebroadleaf = self.c__presence('broadleaf')
        self.v__presencebroadleaftype = self.c__presencetype(50066)
        self.writeSelf(
            [50063, 50064, 50065, 50066],
            [
                self.v__presenceconifer,
                self.v__presenceconifertype,
                self.v__presencebroadleaf,
                self.v__presencebroadleaftype
            ]
        )
        self.isBroadleafForest = self.broadleafForest(
            self.v__presencebroadleaf,
            self.v__presencebroadleaftype
        )
        
        self.v__deadtreespercent = self.c__treeharmindex(50068)
        self.writeSelf(50068, self.v__deadtreespercent)
        self.v__inclinedtreespercent = self.c__treeharmindex(50069)
        self.writeSelf(50069, self.v__inclinedtreespercent)
        self.v__brokentreespercent = self.c__treeharmindex(50070)
        self.writeSelf(50070, self.v__brokentreespercent)
        self.v__brurnttreespercent = self.c__treeharmindex(50071)
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
        
        self.v__degenerationindex = self.c__degenerationindex()
        self.writeSelf(50072, self.v__degenerationindex)
        
        # RELATED TABLES:
        self.v__invasivespecies = self.c__invasivespecies()
        for invSp, epicenter in self.v__invasivespecies.items():
            self.writeRelated(
                'st1',
                [51001,51002],
                [invSp, epicenter]
            )

        self.v__planttype = self.c__planttype()
        for planttype, percent in self.v__planttype.items():
            self.writeRelated('st2', [52001, 52002], [planttype, percent])

        self.v__covtypeRel = self.c__covtypeRel()
        for species, proportion in self.v__covtypeRel:
            self.writeRelated('st3', [53001, 53002], [species, proportion])

        self.v__vitalforest = self.c__vitalforest()
        for defect, impact in self.v__vitalforest.items():
            self.writeRelated('st4', [54001,54002], [defect, impact])

        # RELATED TABLES DESCRIPTION:
        self.v__invasivespecies_desc = self.c__invasivespecies_desc(self.v__invasivespecies)
        self.writeSelf(50074, self.v__invasivespecies_desc)
        self.v__planttype_desc = self.c__planttype_desc(self.v__planttype)
        self.writeSelf(50058, self.v__planttype_desc)
        self.v__covtype_desc = self.c__covtype_desc(self.v__covtypeRel)
        self.writeSelf(50040, self.v__covtype_desc)
        self.v__vitalforest_desc = self.c__vitalforest_desc(self.v__vitalforest)
        self.writeSelf(50073, self.v__vitalforest_desc)

        # BACK TO SELF FIELDS
        # (logiclayer must run after c__planttype)
        self.v__logiclayers = self.c__logiclayers()
        oedered_fieldCodes = {
            #order: [forest layer, veg form, layer cover, layer desc]
            'primary': [50029,50030,50031,50032],
            'secondary': [50033,50034,50035,50036]
        }
        for order, layerResult in self.v__logiclayers.items():
            #oder is the key of the result dict, can be primary/secondary
            #to fit the keys fieldCodes.
            fieldCodes = oedered_fieldCodes[order]
            values = layerResult.getValuesToWrite()
            self.writeSelf(fieldCodes, values)

        self.v__forestagecomposition = self.c__forestagecomposition()
        self.writeSelf(50041, self.v__forestagecomposition)

        self.v__standvegform = self.c__standvegform(self.v__logiclayers)
        self.writeSelf(50037, self.v__standvegform)

        self.v__supSpecies_trees = self.c__subSpecies(50060)
        self.writeSelf(
            [50059,50060],
            [self.v__supSpecies_trees['names'],self.v__supSpecies_trees['codes']]
            )
        self.v__supSpecies_shrubs = self.c__subSpecies(50062)
        self.writeSelf(
            [50061,50062],
            [self.v__supSpecies_shrubs['names'],self.v__supSpecies_shrubs['codes']]
            )

        self.v__naturalvalues = self.c__naturalvalues()
        self.writeSelf(50075, self.v__naturalvalues['main'])
        if self.v__naturalvalues['details']:
            self.writeSelf(50103, self.v__naturalvalues['details'])
        
        self.v__roadsidesconditions = self.c__roadsidesconditions()
        self.writeSelf(50076, self.v__roadsidesconditions['main'])
        if self.v__roadsidesconditions['details']:
            self.writeSelf(50104, self.v__roadsidesconditions['details'])
        
        self.v__limitedaccessibilitytype = self.c__limitedaccessibilitytype()
        self.writeSelf(50077, self.v__limitedaccessibilitytype['main'])
        if self.v__limitedaccessibilitytype['details']:
            self.writeSelf(50105, self.v__limitedaccessibilitytype['details'])
        
        self.v__foresthazards = self.c__foresthazards()
        self.writeSelf(50078, self.v__foresthazards['main'])
        if self.v__foresthazards['details']:
            self.writeSelf(50106, self.v__foresthazards['details'])



        self.v__groundlevelfloorvegform = self.c__groundlevelfloorvegform()
        self.writeSelf(50089, self.v__groundlevelfloorvegform)
        
        self.v__pointvarianceindex = self.c__pointvarianceindex()
        self.writeSelf(50087, self.v__groundlevelfloorvegform)

        return

    def c__density(self, mode):
        """
        Takes density values of source stands.
        Inputs: mode <str> - 'general' / 'stand'.
        Validation: if value is in [None, "לא רלוונטי", "אין עצים"]: notify and return it. 
        Process: weighted sum of index.
        Returns: category <str>
        """
        StepNames = {
            'general': 'generaldensity',
            'stand': 'standdensity'
        }
        fieldCodes = {
            'general': 50042,
            'stand': 50043
        }
        stepName = StepNames[mode]
        fieldCode = fieldCodes[mode]

        domainValues = [
            "לא רלוונטי",
            "אין עצים",
            "1-10",
            "11-20",
            "21-40",
            "41-60",
            "61-100",
            "מעל  100"
        ]

        matrix = self.getMatrix_self(fieldCode)

        # VALIDATION:
        # in case any value is one of the following: [None, "לא רלוונטי", "אין עצים"],
        # notify and return this value.
        exceptionValues = [None] + domainValues[:2]
        inputValues = [tup[1] for tup in matrix]
        for inputValue in inputValues:
            if inputValue in exceptionValues:
                # value is from [null, "לא רלוונטי", "אין עצים"]
                txt = "invalid input value: %s" % inputValue
                self.notifier.add(stepName, 'warning', txt)
                return inputValue
            elif inputValue not in domainValues:
                # value is entirely not from domain AND is not None.
                # notify and return None
                txt = "input value is not from domain: %s" % inputValue
                self.notifier.add(stepName, 'warning', txt)
                return None

        # LOGIC:
        # at this point we are confident that the values are from domainValues[2:]
        weighted_value = normal_round(sum([proportion*domainValues.index(category) for proportion, category in matrix]))
        result = domainValues[weighted_value]
        return result

    def c__relativedensity(self, agegroup, generaldensity, beitgidul):
        """
        Method takes string inputs and inserts them as parameters for
        a 3-dimensional matrix.
        Notice: input values age group and general density are
        previously calculated for this new stand in calculate and write.
        """
        stepName = 'relativedensity'
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

    def c__actualagegroup(self):
        """
        Takes source polygons' values, validates they are among domain values,
        process and return actual age group.
        """
        stepName = 'actualagegroup'

        domainValues = [
            "לא רלוונטי",
            "רב גילי",
            "בהקמה (1)",
            "בהקמה (2)",
            "בהקמה (3)",
            "בהקמה (4)",
            "בהקמה (5)",
            "חדש (6-10)",
            "צעיר (11-15)",
            "צעיר (16-20)",
            "מתבגר (21-25)",
            "מתבגר (26-30)",
            "בוגר (31-40)",
            "בוגר (41-50)",
            "בוגר (51-60)",
            "ותיק (61-75)",
            "ותיק (76-90)",
            "ותיק (91-105)"
        ]
        matrix = self.getMatrix_self(50045)
        #general density of the larger polygon:
        generalDensity_0 = self.stands[0].getSelfData(50042)

        # VALIDATION:
        # valid only if both values are from domainValues[2:]
        validValues_sum = sum([t[1] in domainValues[2:] for t in matrix])
        if validValues_sum == 0:
            txt = "both source values are invalid."
            self.notifier.add(stepName, 'warning', txt)
            return None
        elif validValues_sum == 1:
            # is the invalid value not from domainValues[:2]?
            invalidFromFirstTwo = sum([t[1] in domainValues[:2] for t in matrix]) > 0
            if invalidFromFirstTwo:
                # continue to logic with one value of domainValues[2:].
                # pay attention: the return value might be one of these two,
                # in that case, notify AFTER the logic.
                pass
            else:
                # the invalid value is not from the domain at all.
                invalidValue = [t[1] for t in matrix if t[1] not in domainValues[:2]][0]
                txt = "source value (%s) is not from domain." % invalidValue
                self.notifier.add(stepName, 'warning', txt)
                return None

        # LOGIC:
        result = None
        if self.areaDominance:
            result = matrix[0][1]
        elif generalDensity_0 in ["לא רלוונטי", "אין עצים", None]:
            result = matrix[1][1]
        else:
            seniorIndex = max([domainValues.index(t[1]) for t in matrix])
            result = domainValues[seniorIndex]
        
        # POST-LOGIC VALIDATION:
        if result in domainValues[:2] + [None]:
            # notify and return
            txt = "returns - %s" % result
            self.notifier.add(stepName, 'warning', txt)
        return result

    def c__start_year(self):
        """
        Takes source polygons' values, validates they are intable,
        process and return start year.
        """
        stepName = 'startyear'

        matrix = self.getMatrix_self(50027)
        #general density of the larger polygon:
        generalDensity_0 = self.stands[0].getSelfData(50042)

        # VALIDATION:
        # valid only if both polygons are intable.
        validValues = [t[1] for t in matrix if isIntable(t[1])]
        if len(validValues) == 0:
            # both values are invalid,
            # notify and return None.
            txt = "both of the values of source polygons are not a number."
            self.notifier.add(stepName, 'warning', txt)
            return None
        elif len(validValues) == 1:
            # only one value is valid, return it.
            return validValues[0]

        # LOGIC:
        if self.areaDominance:
            return matrix[0][1]
        elif generalDensity_0 in ["לא רלוונטי", "אין עצים", None]:
            return matrix[1][1]
        else:
            return min([t[1] for t in matrix])
    
    def c__last_year(self):
        """
        Takes source polygons' values, validates they are intable,
        process and return last year.
        """
        stepName = 'lastyear'

        matrix = self.getMatrix_self(50081)
        #general density of the larger polygon:
        generalDensity_0 = self.stands[0].getSelfData(50042)

        # VALIDATION:
        # valid only if both polygons are intable.
        validValues_sum = sum([isIntable(t[1]) for t in matrix])
        if validValues_sum == 0:
            return None
        elif validValues_sum != 2:
            # notify and return None
            isOrAre = ['is', 'are'][validValues_sum-1]
            txt = "%s of the values of source polygons %s not a number." % (validValues_sum, isOrAre)
            self.notifier.add(stepName, 'warning', txt)
            return None

        # LOGIC:
        if self.areaDominance:
            return matrix[0][1]
        elif generalDensity_0 in ["לא רלוונטי", "אין עצים", None]:
            return matrix[1][1]
        else:
            return max([t[1] for t in matrix])

    def c__forestLayer__vegForm(self, layerNum):
        """
        Take all vegForms from forest layers,
        Returns vegForm <int> / <None> according to algorithm.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        """

        layerToFieldCode = {
            4: 50046,
            3: 50050,
            2: 50054,
        }
        priorityVegForms_1 = ['מחטני', 'רחבי-עלים']
        priorityVegForms_2 = ['איקליפטוס', 'שיטים', 'אשלים', 'שיטים פולשני'] 
        stepName = f'layerVegForm_{layerToShortText[layerNum]}'
        fieldCodes = layerToFieldCode[layerNum]
        matrix = self.getMatrix_self(fieldCodes)

        # LOGIC:
        raw_vegForm_0 = matrix[0][1]
        raw_vegForm_1 = matrix[1][1]

        # handle null values -
        # if one of the values is None → return the second value
        # (might also be None).
        if raw_vegForm_0 is None:
            return raw_vegForm_1
        elif raw_vegForm_1 is None:
            return raw_vegForm_0
        # at this point - both values are not None.

        # split, remove spaces, and sort alphabetically to compare
        splitted_vegform_0 = splitAndRemoveSpacesFromEnds(raw_vegForm_0, ',')
        splitted_vegform_0.sort()
        splitted_vegform_1 = splitAndRemoveSpacesFromEnds(raw_vegForm_1, ',')
        splitted_vegform_1.sort()

        sameVegform = splitted_vegform_0 == splitted_vegform_1
        vegForm_pool = removeDup(splitted_vegform_0 + splitted_vegform_1)
        if sameVegform or self.areaDominance:
            # same veg form or forms, including len() == 1
            # - or -
            # area of stand 1 > 80%
            return ','.join(splitted_vegform_0)
        elif len(vegForm_pool) == 2:
            # check if has a mixed (מעורב) veg form.
            # a list of booleans
            isMixed = ['מעורב' in value for value in vegForm_pool]
            if True in isMixed:
                mixedIndex = vegForm_pool.index(True)
                return vegForm_pool[mixedIndex]
            else:
                return ','.join(vegForm_pool)
        else:
            # len () > 2
            # check if any of the the next list is in the pool:
            for vegForm in priorityVegForms_1:
                if vegForm in vegForm_pool:
                    return vegForm
            # check area proportion >= 0.6:
            if self.stands[0].areaProportion >= 0.6:
                return ','.join(splitted_vegform_0)
            # same as before, using a different list:
            for vegForm in priorityVegForms_2:
                if vegForm in vegForm_pool:
                    return vegForm
            else:
                return None

    def c__forestLayer__layerCover(self, layerNum):
        """
        Takes cover categories from source polygons' forest layers,
        sum their (area proportion * cover median) and returns
        cover category of product polygon.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        Returns layer cover <str>.
        """
        layerToFieldCode = {
            4: 50047,
            3: 50051,
            2: 50055
        }
        stepName = f'layerCover_{layerToShortText[layerNum]}'
        fieldCode = layerToFieldCode[layerNum]
        matrix = self.getMatrix_self(fieldCode)
        # the index of 'אין' in layerCover_table1
        defaultLayerCover_key = 'אין'
        domainValues = layerCover_table1.keys()

        # VALIDATION & ORGANIZING:
        validTuples = []
        for proportion, rawValue in matrix:
            # None value means zero
            if rawValue is None:
                # replace with the empty (=zero) placeholder
                tup = (proportion, defaultLayerCover_key)
                validTuples.append(tup)
            # validate covers are from domain values
            elif rawValue not in domainValues:
                # notify and skip tuple
                txt = 'invalid value %s.' % rawValue
                self.notifier.add(stepName, 'warning', txt)
            else:
                # rawValue is from domainValues
                tup = (proportion, rawValue)
                validTuples.append(tup)

        # LOGIC:
        if validTuples:
            weighted_value = sum([proportion*layerCover_table1[category][1] for proportion, category in validTuples])
            result = toCategory(weighted_value, layerCover_table1_backwardsList)
            return result
        else:
            return defaultLayerCover_key

    def c__forestLayer__species(self, layerNum):
        """
        Takes all the species codes from layers of layerNum, among all
        the input stands.
        #@ multiply by area proportion?
        Finds the 3 most frequent species codes, matches them with
        their species names.
        returns a dict of the 3 most frequent codes and names
        ready to be used as string to applied as field value.
        - layerNum - 4 / 3 / 2 <int> (tmira, high, mid. respectively).
        """

        # empty output dict:
        outdict = {
            'codes': None,
            'names': None
        }

        layerToFieldCode = {
            # layer num: spCode field code,
            4: 50049,
            3: 50053,
            2: 50057
        }
        stepName = f'species_{layerToShortText[layerNum]}'
        fieldCode = layerToFieldCode[layerNum]
        species_matrix = self.getMatrix_self(fieldCode)
        vegForm = self.layerVegForm[layerNum]

        """
        ### demo data ###
        species_matrix = [
            (0.4, '1103,1204,1202'),
            (0.6, '1103,1105,3042,2113')
        ]
        vegForm = 'מחטני,רחבי-עלים'
        self.areaDominance = False
        ### end of demo data ###
        """
        """
        Dictionary to coordinate between valid possible values of
        veg form (keys) and their JSON species super-group (values).
        The source of these values is from the output of "unite points"
        for fields 50046, 50050, 50054. More specifically - a list of
        raw point values, after translation
        (e.g, "שיטים_פולשני" to "שיטים פולשני").
        """
        vegForm_validValues = {
            'מחטני': '1000',
            'חורש': '3900',
            'רחבי-עלים': '2900',
            'בוסתנים ומטעים': '2990',
            'שיטים': '2200',
            'שיטים פולשני': '2250',
            'איקליפטוס': '2100',
            'יער גדות נחלים': '3935',
            'אשלים': '3060',
        }
        organizingVegForm_hierarchy = [
            ['מחטני', 'רחבי-עלים'],
            'מחטני',
            'רחבי-עלים',
            'איקליפטוס',
            'שיטים',
            'אשלים',
            'שיטים פולשני'
        ]

        # VALIDATION:
        # vegForm must be from valid values:
        if hasattr(vegForm,'split') and vegForm != '':
            vegForms = []
            for vegForm_split in vegForm.split(','):
                if vegForm_split in vegForm_validValues.keys():
                    vegForms.append(vegForm_split)
                else:
                    txt = 'invalid vegForm value "%s".' % vegForm_split
                    self.notifier.add(stepName, 'warning', txt)
        else:
            # vegForm is not anything to work with - return empty dict.
            return outdict

        if not vegForms:
            # no valid vegForm found - return empty dict.
            return outdict
        
        # species codes: every raw value has to be:
        # 1) splittable into intable items
        # 2) found in speciesDict
        
        # [[species codes <int> of 1st stand], [species codes <int> of 2nd stand]]
        speciesCodes_byStand = []
        for areaProportion, speciesCodes_raw in species_matrix:
            stand_speciesCodes = []
            if hasattr(speciesCodes_raw,'split') and speciesCodes_raw != '':
                speciesCodes_split = speciesCodes_raw.split(',')
                #remove unwanted ' ' spaces from all splitValues:
                speciesCodes_split = [splitVal.replace(' ', '') for splitVal in speciesCodes_split]
                for speciesCode_raw in speciesCodes_split:
                    if isIntable(speciesCode_raw):
                        speciesCode = int(speciesCode_raw)
                        if speciesCode in speciesDict.keys():
                            stand_speciesCodes.append(speciesCode)
                        else:
                            # notify that species code is not found in species JSON:
                            txt = 'Species code value (%s) is not found in: "%s".'\
                            % (speciesCode, speciesDict['__jsonFileName__'])
                            self.notifier.add(stepName, 'warning', txt)
            speciesCodes_byStand.append(stand_speciesCodes)
        # at this point at least one species must be found in both stands:
        if not speciesCodes_byStand[0] and not speciesCodes_byStand[1]:
            # no valid species is found - return empty dict.
            return outdict
        

        # LOGIC:
        # area dominance, and the dominant stand has species codes
        if self.areaDominance and speciesCodes_byStand[0]:
            speciesCodes = speciesCodes_byStand[0]
            speciesNames = [speciesDict[code] for code in speciesCodes]
            outdict = {
                'codes': ','.join([str(x) for x in speciesCodes]),
                'names': ','.join([str(x) for x in speciesNames])
            }
            return outdict

        # find organizing vegForm/s:
        organizing_vegForms = []
        for inspected_vegForm in organizingVegForm_hierarchy:
            if type(inspected_vegForm) is list:
                # vegForms must include all the vegForms from inspected_vegForm list
                includesAll = False not in [inspected in vegForms for inspected in inspected_vegForm]
                if includesAll:
                    organizing_vegForms = inspected_vegForm
                    # found - break from loop
                    break
            elif inspected_vegForm in vegForms:
                # found - break from loop
                organizing_vegForms.append(inspected_vegForm)
                break
        
        if not organizing_vegForms:
            # none of the output stand veg forms appears in organizingVegForm_hierarchy.
            # return empty dict.
            return outdict
        
        # get organizing_vegForms's group species codes
        organizing_groupSpeciesCodes = [vegForm_validValues[org_vegForm] for org_vegForm in organizing_vegForms]

        # use species, area proportions, and organizing_vegForms
        # to create a preferences table:

        # {speciesGroupCode: {speciesCode <int>: sum of area proportions <float>, ...}, ...}
        species_areaSums = {speciesGroupCode:{} for speciesGroupCode in organizing_groupSpeciesCodes}
        for i, speciesCodes in enumerate(speciesCodes_byStand):
            areaProportion = species_matrix[i][0]
            for speciesCode in speciesCodes:
                # check if this species belongs to species representation of vegForm,
                # or belongs to any of its children.
                node = findNode(root,str(speciesCode))
                for speciesGroupCode in organizing_groupSpeciesCodes:
                    if isOrIsChildOf_code(node, speciesGroupCode):
                        # species belongs to the organizing species group
                        # can add its area proportion
                        if speciesCode in species_areaSums[speciesGroupCode].keys():
                            species_areaSums[speciesGroupCode][speciesCode] += areaProportion
                        else:
                            species_areaSums[speciesGroupCode][speciesCode] = areaProportion
        
        # omit species groups that don't contain species:
        species_areaSums = {key:value for key, value in species_areaSums.items() if value != {}}

        # divide each area sum by N species in group (modify species_areaSums)
        for speciesGroupCode, speciesSumArea_dict in species_areaSums.items():
            nSpeciesInGroup = len(speciesSumArea_dict)
            if nSpeciesInGroup > 1:
                speciesSumArea_dict_modified = {key:value/nSpeciesInGroup for key, value in speciesSumArea_dict.items()}
                species_areaSums[speciesGroupCode] = speciesSumArea_dict_modified
        
        # get species count:
        speciesCount = sum([len(speciesGroupCode.keys()) for speciesGroupCode in species_areaSums.values()])
        speciesGroupCount = len(species_areaSums.keys())

        if speciesCount == 0:
            # no species found - return empty dict
            return outdict
        elif speciesCount <= 3 or speciesGroupCount == 1:
            # collect species codes, sort by weightedValue and return
            # [(speciesCode <int>, weightedValue <float>), ...]
            speciesTuples = []
            for species_weightedValue_dict in species_areaSums.values():
                for speciesCode, weightedValue in species_weightedValue_dict.items():
                    tup = (speciesCode, weightedValue)
                    speciesTuples.append(tup)
            # sort by weightedValue (descending)
            speciesTuples.sort(key=lambda x: x[1], reverse = True)
            # limit sumber of species to 3:
            # (since they all belong to the same species group it is allowed to do it arbitrarily)
            speciesCodes = [tup[0] for tup in speciesTuples][:3]
            speciesNames = [speciesDict[c] for c in speciesCodes]
            outdict = {
                'codes': ','.join([str(x) for x in speciesCodes]),
                'names': ','.join([str(x) for x in speciesNames])
            }
            return outdict
        else:
            # output must:
            # 1) limited to 3 species,
            # 2) include species from all the organizing veg form groups (if > 1 group).
            # {speciesGroupCode: [(speciesCode <int>, weightedValue <float>, speciesGroupCode <str>), ...], ...}
            speciesTuples = []
            for speciesGroupCode, species_weightedValue_dict in species_areaSums.items():
                for speciesCode, weightedValue in species_weightedValue_dict.items():
                    tup = (speciesCode, weightedValue, speciesGroupCode)
                    speciesTuples.append(tup)
            # sort by weightedValue (descending)
            speciesTuples.sort(key=lambda x: x[1], reverse = True)
            # outputTuples is first created with the top 2 weighted value species -
            outputTuples = speciesTuples[:2]
            group_heterogeneous = outputTuples[0][2] != outputTuples[1][2]
            if group_heterogeneous:
                # the output species already include species from both species groups,
                # it is okay to take the 3rd
                outputTuples.append(speciesTuples[2])
            else:
                # the last tuple must be of different species group.
                homogeneous_group = outputTuples[0][2]
                # look for the next species from species that are not yet selected.
                for tup in speciesTuples[2:]:
                    tupGroup = tup[2]
                    if tupGroup != homogeneous_group:
                        outputTuples.append(tup)
                        # add only one:
                        break
            
            speciesCodes = [tup[0] for tup in outputTuples]
            speciesNames = [speciesDict[c] for c in speciesCodes]
            outdict = {
                'codes': ','.join([str(x) for x in speciesCodes]),
                'names': ','.join([str(x) for x in speciesNames])
            }
            return outdict


    def c__totalcoverage(self):
        stepName = 'totalcoverage'

        domainValues = list(layerCover_table1.keys())

        fieldCode = 50088
        matrix = self.getMatrix_self(fieldCode)
        valid_tuples = []

        # VALIDATION:
        for proportion, raw_value in matrix:
            if raw_value in domainValues:
                valid_tuples.append((proportion, raw_value))
            elif raw_value is not None:
                fieldAlias = fieldsDict[fieldCode].alias
                txt = 'invalid value (%s) in field "%s".' % (raw_value, fieldAlias)
                self.notifier.add(stepName, 'warning', txt)

        # LOGIC:
        weighted_value = sum([proportion*layerCover_table1[category][1] for proportion, category in matrix])
        result = toCategory(weighted_value, layerCover_table1_backwardsList)

        return result

    def c__presencetype(self, fieldCode):
        """
        Takes a field code, gets its data, and combining the different
        values without duplications acording to the domain "s_PresenceType".
        """
        stepName = 'presencetype'

        domainValues = [
            'אין',
            'התחדשות_טבעית',
            'נטיעה',
            'נטיעה,התחדשות_טבעית'
        ]

        matrix = self.getMatrix_self(fieldCode)
        raw_values = [value for area, value in matrix]
        # use set to avoid duplications
        valid_values = set()
        
        # VALIDATION:
        for raw_value in raw_values:
            if not hasattr(raw_value, 'split'):
                continue
            else:
                spit_values = raw_value.split(',')
                for split_value in spit_values:
                    if split_value in domainValues:
                        valid_values.add(split_value)
                    elif split_value is not None:
                        fieldAlias = fieldsDict[fieldCode].alias
                        txt = 'invalid value (%s) in field "%s".' % (split_value, fieldAlias)
                        self.notifier.add(stepName, 'warning', txt)
        
        # LOGIC:
        if valid_values:
            valid_values = list(valid_values)
            if domainValues[3] in valid_values:
                return domainValues[3]
            elif domainValues[1] in valid_values and domainValues[2] in valid_values:
                return domainValues[3]
            elif domainValues[1] in valid_values:
                return domainValues[1]
            elif domainValues[2] in valid_values:
                return domainValues[2]
            else:
                return domainValues[0]
        else:
            # return the default value 'אין'.
            return domainValues[0]

    def c__treeharmindex(self, fieldCode):
        """
        Not to be confused with treeharm field.
        Takes values of harm rank from one of the fields:
            -DeadTreesPercent
            -InclinedTreesPercent
            -BrokenTreesPercent
            -BrurntTreesPercent
        takes each category's median, multiply by area proportion, sum
        and return the matching category.
        """
        fieldName = fieldsDict[fieldCode].name
        stepName = "tree harm index: %s" % fieldName
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
        
        matrix = self.getMatrix_self(fieldCode)

        # VALIDATE:

        # a list of category median multiplied by area proportion
        validMediansToProportion = []
        for areaProportion, category in matrix:
            category_isValid = category in domainValues.keys()
            if category_isValid:
                medianValue = domainValues[category][0]
                weightedValue = areaProportion*medianValue
                validMediansToProportion.append(weightedValue)
            elif category is None:
                #A notification is not necessary.
                continue
            else:
                #category is not valid nor none → notify as warning.
                txt = "Invalid value insource polygon field '%s': %s." % (fieldName, category)
                self.notifier.add(stepName, 'warning', txt)
        
        # LOGIC:
        if validMediansToProportion:
            weightedSum = sum(validMediansToProportion)
            category = toCategory(weightedSum, backwardsList)
            return category
        else: 
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

    def c__subSpecies(self, codesFieldCode):
        """
        Takes group cover, area proportion, and species list
        of every source stand, 
        calculates each species weighted value,
        return top 3 species codes and names.
        - codesFieldCode <int>: 50060 (trees) or 50062 (shrubs).
        """
        stepNames = {
            50060: 'trees',
            50062: 'shrubs'
        }
        stepName = 'species-%s' % stepNames[codesFieldCode]
        planttypeKeys = {
            50060: 'עצים',
            50062: 'שיחים'
        }
        planttypeKey = planttypeKeys[codesFieldCode]

        
        matrix_species = self.getMatrix_self(codesFieldCode)
        matrix_covers = self.getMatrix_related('st2', [52001,52002])

        ### demo data ###
        """
        matrix_species = [
            (0.4, '4121,8027,9018'),
            (0.6, '9018,4121,4161')
        ]
        matrix_covers = [
            (0.4, [(planttypeKey, 50)]),
            (0.6, [(planttypeKey, 20)])
        ]
        ### end of demo data ###
        """

        # LOGIC BEFORE VALIDATON:
        # in case of area proportion of larger stand is >= 80%
        if self.areaDominance:
            # return values of the larger stand without changing
            fieldCodes = {
                50060: [50060,50059],
                50062: [50062,50061]
            }
            matrix = self.getMatrix_self(fieldCodes[codesFieldCode])
            dominantStand_values = matrix[0][1]
            outdict = {
                'codes': dominantStand_values[0],
                'names': dominantStand_values[1]
            }
            return outdict

        # VALIDATION & ORGANIZING:
        # species-focused
        # create a dict of {species code <int>: [(area proportion <float>, cover <int>), ...], ...}
        speciesTable = {}
        for stand_i in range(len(matrix_species)):
            # get cover:
            # a single cover value for all the species in the stand.
            # set a default cover
            stand_cover = 0
            try:
                rawValues = matrix_covers[stand_i][1]
                stand_cover = int([tup[1] for tup in rawValues if tup[0] == planttypeKey][0])
            except:
                sourceStandID = self.stands[stand_i].id
                txt = 'unable to get cover of %s from planttype related table (source stand ID: %s)' \
                    % (planttypeKey, sourceStandID)
                self.notifier.add(stepName, 'warning', txt)
                
            # get species list:
            # stand_species = [speciesCode <int>, ...]
            rawValue = matrix_species[stand_i][1]
            stand_species = []
            if hasattr(rawValue, 'split') and rawValue != '':
                rawValue_splitted = rawValue.split(',')
                for splitValue in rawValue_splitted:
                    if isIntable(splitValue):
                        if int(splitValue) in speciesDict.keys():
                            stand_species.append(int(splitValue))
                        else:
                            sourceStandID = self.stands[stand_i].id
                            txt = "Species code %s wasn't found in species list. source stand id: %s." \
                                % (splitValue, sourceStandID)
                            self.notifier.add(stepName, 'warning', txt)
                    else:
                        sourceStandID = self.stands[stand_i].id
                        txt = "Species code %s failed to be turned into an integer. source stand id: %s." \
                            % (splitValue, sourceStandID)
                        self.notifier.add(stepName, 'warning', txt)

            # append the final tuple: (area, cover)
            areaProportion = matrix_species[stand_i][0]
            newTup = (areaProportion, stand_cover)
            for species in stand_species:
                if species in speciesTable.keys():
                    speciesTable[species].append(newTup)
                else:
                    speciesTable[species] = [newTup]

        # LOGIC:
        # for every species: calculate its weighted value
        # [(speciesCode <int>, weighted value <float>), ...]
        speciesRanks = []
        for speciesCode, tupList in speciesTable.items():
            size_sum = sum([tup[0] for tup in tupList])
            cover_sum = sum([tup[0]*tup[1] for tup in tupList])
            weightedValue = size_sum * cover_sum
            newTup = (speciesCode, weightedValue)
            speciesRanks.append(newTup)
        
        # sort by weighted value (descending)
        speciesRanks.sort(key=lambda x: x[1], reverse = True)
        # weightedValue must be > 0
        codes = [speciesCode for speciesCode, weightedValue in speciesRanks if weightedValue > 0][:3]
        names = [speciesDict[code] for code in codes]
        outdict = {
            'codes': ','.join([str(x) for x in codes]),
            'names': ','.join([str(x) for x in names])
        }
        return outdict
        
    def c__naturalvalues(self):
        """
        Removes None and "אין" values,
        if other values exist → remove duplications → concatenate,
        else: return "אין"
        """
        stepName = 'naturalvalues'

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

        matrix = self.getMatrix_self(50075)

        # VALIDATION:
        validValues = []
        for polygonTup in matrix:
            rawValue = polygonTup[1]
            if rawValue in domainValues:
                validValues.append(rawValue)
        
        # convert to indexes:
        indexList = [domainValues.index(rv) for rv in validValues]
        # indexes to be removed:
        for indexToRemove in [0, 1]:
            while indexToRemove in indexList:
                indexList.remove(indexToRemove)
        
        # LOGIC:
        if indexList:
            #sort by frequency, remove duplications.
            indexList_sorted = freqSorted(indexList)
            #convert indexes back to values:
            valList = [domainValues[i] for i in indexList_sorted]
            if elseValue in valList:
                #1) move elseValue to end (if exists)
                valList = makeLast(valList, elseValue)
                #2) copy free text from the details field
                details_matrix = self.getMatrix_self(50103)
                detailsList = [tup[1] for tup in details_matrix]
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
        stepName = 'roadsidesconditions'

        valuesToOmit = ["", " "]
        defaultValue = "תקין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        matrix = self.getMatrix_self(50076)

        # VALIDATION:
        validValues = []
        for polygonTup in matrix:
            #rawValues is a list of row values (string),
            #each string is a concatenation with ","s.
            rawValue = polygonTup[1]
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = splitAndRemoveSpacesFromEnds(rawValue, ',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        # LOGIC:
        if validValues:
            #sort by frequency, remove duplications
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                details_matrix = self.getMatrix_self(50104)
                detailsList = [tup[1] for tup in details_matrix]
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
        stepName = 'limitedaccessibilitytype'

        valuesToOmit = ["", " "]
        defaultValue = "אין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        matrix = self.getMatrix_self(50077)

        # VALIDATION:
        validValues = []
        for polygonTup in matrix:
            #rawValues is a list of row values (string),
            #each string is a concatenation with ","s.
            rawValue = polygonTup[1]
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = splitAndRemoveSpacesFromEnds(rawValue, ',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        # LOGIC:
        if validValues:
            #sort by frequency, remove duplications
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                details_matrix = self.getMatrix_self(50105)
                detailsList = [tup[1] for tup in details_matrix]
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
        If "אין" coexists with other values - remove it.
        """
        stepName = 'foresthazards'

        valuesToOmit = ["", " "]
        defaultValue = "אין"
        elseValue = "אחר"
        resultsDict = {
            'main': defaultValue,
            'details': None
        }

        matrix = self.getMatrix_self(50078)

        # VALIDATION:
        validValues = []
        for polygonTup in matrix:
            #rawValues is a list of row values (string),
            #each string is a concatenation with ","s.
            rawValue = polygonTup[1]
            if rawValue:
                #rawValue of None/""/" " won't get here.
                splitList = splitAndRemoveSpacesFromEnds(rawValue, ',')
                for splitValue in splitList:
                    if splitValue not in valuesToOmit:
                        validValues.append(splitValue)
        
        # LOGIC:
        if validValues:
            #sort by frequency, remove duplications
            validValues_sorted = freqSorted(validValues)
            if elseValue in validValues_sorted:
                #1) move elseValue to end (if exists)
                validValues_sorted = makeLast(validValues_sorted, elseValue)
                #2) copy free text from the details field
                details_matrix = self.getMatrix_self(50106)
                detailsList = [tup[1] for tup in details_matrix]
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

    def c__degenerationindex(self):
        """
        Calculate stand's vital cover average, and return its category <str>.
        """
        stepName = 'degenerationindex'

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
        matrix = self.getMatrix_self(50072)

        # VALIDATION:
        validTuples = []
        for i, polygonTup in enumerate(matrix):
            value = polygonTup[1]
            if value in domainValues:
                validTuples.append(polygonTup)
            elif value is not None:
                stand_ID = self.stands[i].id
                txt = 'value (%s) from field (stand id %s) is invalid.' % (value, stand_ID)
                self.notifier.add(stepName, 'warning', txt)
        
        # LOGIC:
        if validTuples:
            weighted_value = sum([areaProportion*domainValues[category][0] for areaProportion,category in validTuples])
            resultCategory = toCategory(weighted_value, backwardsList)
            return resultCategory
        else:
            return defaultValue


    def c__presence(self, mode):
        """
        Takes mode as method input. 
        Different modes have different field codes and domain values.
        Process: weighted sum of index.
        Input:
        - mode <str>: 'conifer' / 'broadleaf'.
        Returns: category <str>
        """
        stepName = 'presenceconifertype'

        domainValues_dict = {
            'conifer': [
                'אין',
                '1-20',
                '21-50',
                '51-100',
                'מעל 100 '
            ],
            'broadleaf': [
                'אין',
                '1-5',
                '6-10',
                '11-20',
                'מעל 20 '
            ]
        }
        fieldCode_dict = {
            'conifer': 50063,
            'broadleaf': 50065
        }

        domainValues = domainValues_dict[mode]
        fieldCode = fieldCode_dict[mode]

        matrix = self.getMatrix_self(fieldCode)
        valid_tuples = []

        # VALIDATION:
        for proportion, raw_value in matrix:
            if raw_value in domainValues:
                valid_tuples.append((proportion, raw_value))
            elif raw_value is not None:
                fieldAlias = fieldsDict[fieldCode].alias
                txt = 'invalid value (%s) in field "%s".' % (raw_value, fieldAlias)
                self.notifier.add(stepName, 'warning', txt)

        # LOGIC:
        if valid_tuples:
            #numerator = sum of (area proportion * index)
            numerator = sum([proportion*domainValues.index(category) for proportion, category in valid_tuples])
            #denominator = sum of area proportions, equals 1 if len(valid_tuples) == 2.
            denominator = sum([proportion for proportion, category in valid_tuples])
            quotient = normal_round(numerator/denominator)
            result = domainValues[quotient]
            return result
        else:
            # return the default value 'אין'.
            return domainValues[0]

    def c__invasivespecies(self):
        """
        Takes rows from invasive species related table,
        for every unique invasive species - 
        in case it appears in both polygons - take the bigger epicenter.
        Returns a dict of {incasive species <str>: epicenter <str>, ...}
        """
        stepName = 'invasivespecies'

        # import the domain instead of explicitly write it
        domainValues_invasiveSpecies = listCodedValues(org.stands.workspace, fieldsDict[51001].domain)
        domainValues_epicenter = [
            'אין',
            'מוקד קטן',
            'מוקד בינוני',
            'מוקד גדול',
        ]
        default_empty_dict = {'אין': 'אין'}

        matrix = self.getMatrix_related('st1', [51001,51002])

        # VALIDATION & ORGANIZING:
        valid_Tuples = [] #all valid [(invasiveSp, epicenter), ...]

        for polygon in matrix:
            rows = polygon[1]
            for invasiveSp, epicenter in rows:
                invasiveSp_valid = True
                epicenter_valid = True
                empty_valid = True

                # validate invasiveSp:
                if invasiveSp is None:
                    invasiveSp_valid = False
                elif invasiveSp not in domainValues_invasiveSpecies:
                    txt = 'invasive species (%s) does not appear in domain.'
                    self.notifier.add(stepName, 'warning', txt)
                    invasiveSp_valid = False

                # validate epicenter:
                if epicenter is None:
                    epicenter_valid = False
                elif epicenter not in domainValues_epicenter:
                    txt = 'epicenter (%s) does not appear in domain.'
                    self.notifier.add(stepName, 'warning', txt)
                    epicenter_valid = False
                
                # validate empty tuples:
                if 'אין' in [invasiveSp, epicenter]:
                    # skip any case of epicenter or invasive species is 'אין'
                    empty_valid = False
                
                # end validation:
                if invasiveSp_valid and epicenter_valid and empty_valid:
                    tup = (invasiveSp, epicenter)
                    valid_Tuples.append(tup)
                else:
                    # for readability,
                    # code-wise it is redundant redundant
                    continue

        # LOGIC:
        if valid_Tuples:
            result_dict = {} # {invasiveSp: biggest epicenter, ...}
            for invasiveSp, epicenter in valid_Tuples:
                if invasiveSp not in result_dict.keys():
                    result_dict[invasiveSp] = epicenter
                else:
                    existingEpicenter_index = domainValues_epicenter.index(result_dict[invasiveSp])
                    newEpicenter_index = domainValues_epicenter.index(epicenter)
                    if newEpicenter_index > existingEpicenter_index:
                        result_dict[invasiveSp] = epicenter
            # dict to list of tuples:
            #@ deprecated:
            #result_list = [(invasiveSp, epicenter) for invasiveSp, epicenter in result_dict.items()]
            return result_dict
        else:
            return default_empty_dict

    def c__planttype(self):
        """
        Takes plant type rows from related table of source polygons,
        validates their values, and multiply them by the area proportion
        of their polygon.
        Returns a dictionary of every plant type & its percent:
        {plant type 1 <int>: percent <int>, ...}
        """
        stepName = 'planttype'
        # Empty dictionary:
        plantType_valuesList = {
            "צומח_גדות_נחלים": [],
            "עצים": [],
            "שיחים": [],
            "בני_שיח": [],
            "עשבוני": [],
            "ללא_כיסוי": [],
            "מינים_פולשים": []
        }
        matrix = self.getMatrix_related('st2', [52001,52002])

        # VALIDATION & ORGANIZING:
        for polygon in matrix:
            proportion = polygon[0]
            rows = polygon[1]
            # validation includes: 
            # 1 - plant type is from recognized categories (mandatory),
            # 2 - percent is intable (mandatory), 
            # 3 - int of percent is a multiple of 10,
            
            # create an empty dict based on plantType_valuesList keys:
            polygon_plantTypeDict = {pType:0 for pType in plantType_valuesList.keys()}

            for plantType, percent in rows:
                try:
                    polygon_plantTypeDict[plantType] += int(percent)
                    if int(percent) % 10 != 0:
                        txt = 'percent (%s) of input polygon is not a multiple of 10.' % percent
                        self.notifier.add(stepName, 'warning', txt)
                except KeyError:
                    txt = 'plant type (%s) of input polygon is invalid.' % plantType
                    self.notifier.add(stepName, 'warning', txt)
                except ValueError:
                    txt = 'percent (%s) of input polygon is not convertable to number.' % percent
                    self.notifier.add(stepName, 'warning', txt)# --- end of validation ---

            # append the sum of every plant type to plantType_valuesList[plantType]
            for plantType, percent in polygon_plantTypeDict.items():
                # each polygon gets one value in plantType_valuesList
                # correspond to its order within self.stands.
                plantType_valuesList[plantType].append(percent)
        
        # LOGIC:
        # output dictionary:
        plantTypeDict = {}
        for plantType, valuesList in plantType_valuesList.items():
            # calculate a weighted value by 
            # multiplying each value with its area proportion.
            weightedValues = [percent*self.stands[i].areaProportion for i, percent in enumerate(valuesList)]
            weightedValue = sum(weightedValues)
            # round to nearest 10
            roundedValue = int(10*normal_round(weightedValue/10))
            plantTypeDict[plantType] = roundedValue
        # 
        percentSum = sum(plantTypeDict.values())
        if percentSum < 100:
            # modify to make sum == 100, while preserving ratios
            ratio = 100/percentSum
            plantTypeDict = {pType: percent*ratio for pType, percent in plantTypeDict.items()}
            # convert to list before passing to function
            plantTypes = []
            percents = []
            for pType, percent in plantTypeDict.items():
                plantTypes.append(pType)
                percents.append(percent)
            percents_rounded = roundToNearestBase(percents,10)
            plantTypeDict = {plantTypes[i]:percents_rounded[i] for i in range(len(plantTypes))}
        return plantTypeDict

    def c__covtypeRel(self):
        """
        Takes covtype species and proportions from source polygons'
        related tables, calculates each species' weighted value,
        and round the numbers to
        Returns a list of tuples [(species, proportion), ...]
        """
        stepName = 'covtypeRel'
        
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
        domainValues = listCodedValues(arcpy.env.workspace, fieldsDict[53001].domain)

        matrix = self.getMatrix_related('st3', [53001,53002])
        generalDensity_matrix = self.getMatrix_self(50042)

        """
        #@ debug data:
        matrix = [
            (
                0.63,
                [
                    ('1103', 9),
                    ('1200', 1)
                ]
            ),
            (
                0.37,
                [
                    ('1105', 1),
                    ('1103', 7),
                    ('3111', 1),
                    ('2910', 1)
                ]
            )
        ]
        generalDensity_matrix = [
            (0.63, "21-40"),
            (0.37, "11-20")
        ]
        """

        resultsDict = {}

        # VALIDATION & ORGANIZING:
        # 1 - domTree appears in the domain possibilities (notify if not),
        # 2 - proportion is intable (mandatory)
        for polygonIndex, polygon in enumerate(matrix):
            areaProportion = polygon[0]
            rows = polygon[1]
            polygon_Generaldensity_median = generalDensity_medians[generalDensity_matrix[polygonIndex][1]]
            for domTree, proportion in rows:
                # validation
                if domTree not in domainValues:
                    txt = 'tree code (%s) of input polygon does not appear in domain.' % domTree
                    self.notifier.add(stepName, 'warning', txt)
                try:
                    weightedValue = int(proportion)*areaProportion*polygon_Generaldensity_median
                except ValueError:
                    txt = 'percent (%s) of input polygon is not convertable to number.' % proportion
                    self.notifier.add(stepName, 'warning', txt)
                # --- end of validation ---

                if domTree in resultsDict.keys():
                    resultsDict[domTree] += weightedValue
                else:
                    resultsDict[domTree] = weightedValue

        # LOGIC:
        totalSum = sum(resultsDict.values())
        if totalSum != 0:
            domTrees = []
            proportions = []
            for domType, proportion in resultsDict.items():
                domTrees.append(domType)
                # notice I devide by total sum, and multiply by 10,
                # to make the proportion 10-based.
                proportions.append(10*proportion/totalSum)
            percents_rounded = roundToNearestBase(proportions, 1)
            # remove zeros
            resultsDict = [tuple([domTrees[i],str(percents_rounded[i])]) for i in range(len(domTrees)) if percents_rounded[i]!=0]
            return resultsDict
        else:
            return []

    def c__vitalforest(self):
        """
        Takes values from vital forest related tables,
        after validation, each impact median is multiplied by 
        its polygon's area proportion. The next step is to sum
        this number for each defect, and then convert the sum
        to category.
        Returns:
        defectsCategories = {forest defect <str>: percent impact <str>, ...}
        ---------------
        #@ this method does not deal with defect 'אחר' yet.
        """
        stepName = 'vital forest'

        defects_domainValues = [
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
        impact_table = {
            'אין': (0, 0),
            'זניח (3%-0%)': (2, 3),
            'מועט (10%-3%)': (7, 10),
            'בינוני (33%-10%)': (22, 33),
            'גבוה (66%-33%)': (50, 66),
            'גבוה מאוד (מעל 66%)': (88, 100)
        }
        impact_table_backwardsList = [(v[1],k) for k,v in impact_table.items()]

        elseValue = defects_domainValues[len(defects_domainValues)-1] #(last)

        matrix = self.getMatrix_related('st4', [54001,54002])

        # VALIDATION & ORGANIZING:
        # 1 - defect appears in domain possibilities (notify if not),
        # 2 - percent impact appears in impact_table
        # defectsAndSums = {forest defect <str>: sum(median*areaProportion) <float>}
        defectsAndSums = {}
        for polygon_tup in matrix:
            polygon_areaProportion = polygon_tup[0]
            for row_tup in polygon_tup[1]:
                defect = row_tup[0]
                impact = row_tup[1]
                if defect not in defects_domainValues:
                    txt = 'invalid value %s - not from domain.' % defect
                    self.notifier.add(stepName, 'warning', txt)
                    continue
                elif defect == elseValue:
                    #@ impact == אחר...
                    continue
                else:
                    # the defect value is from the domains AND is not elseValue.
                    # validate impact:
                    impact_isValid = impact in impact_table.keys()
                    if impact_isValid:
                        # calculate with area proportion and add to dictionary.
                        impactMedian = impact_table[impact][0]
                        if impactMedian == 0:
                            # don't calculate it the impact median is 0.
                            continue
                        currentResult = polygon_areaProportion * impactMedian
                        if defect in defectsAndSums.keys():
                            defectsAndSums[defect] += currentResult
                        else:
                            defectsAndSums[defect] = currentResult
                    else:
                        txt = 'invalid value %s - not from domain.' % impact
                        self.notifier.add(stepName, 'warning', txt)
                        continue
        
        # LOGIC:
        # at this point defectsAndSums should has the data,
        # if it does - convert every sum of impact to category.
        
        #defectsCategories is the dict to be returned
        #defectsCategories = {forest defect <str>: percent impact <str>, ...}
        defectsCategories = {}
        for defect, sumImpact in defectsAndSums.items():
            category = toCategory(sumImpact, impact_table_backwardsList)
            defectsCategories[defect] = category

        return defectsCategories

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
        tupList = [(k,v) for k,v in invasivespeciesDict.items()]
        #Sort by the index of the epicenterType (magnitude):
        tupList.sort(key=lambda x: epicenterType_sorted.index(x[1]), reverse = True)

        #strList = ["defect type 1 - percent impact", "defect type 2 - percent impact"]
        strList = []
        for tup in tupList:
            invasiveSpecies = tup[0]
            epicenterType = tup[1]
            txt = "%s - %s" % (invasiveSpecies, epicenterType)
            strList.append(txt)
        
        if strList:
            concat = ", ".join(strList)
            return concat
        else:
            return None

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

    def c__logiclayers(self):
        """
        Calculates product stand's primary and secondary layers' attributes:
        forest layer, veg form, layer cover, layer desc.
        """
        stepName = 'logiclayers'
        #The method returns outDict
        outDict = {
            "primary": LayerResult(),
            "secondary": LayerResult()
        }

        #This step is unique to unite stands, as polygon layers are
        #created during calculateandwrite.
        self.layers = self.setLayers()

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
            planttype = {k:v for k,v in self.v__planttype.items()}
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

        # VALIDATION:
        # Keep only values that can be indexed later.
        validValues = []
        for rawValue in rawValues:
            if rawValue in layerCoverKeys:
                validValues.append(rawValue)
        
        # LOGIC:
        indexedValues = [layerCoverKeys.index(v) for v in validValues]
        N_valuesAboveThreshold = len([index_ for index_ in indexedValues if index_ >= thrasholdIndex])
        return optionsToReturn[N_valuesAboveThreshold]

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

    def c__pointvarianceindex(self):
        """
        Takes values of an array of fields from all the sekerpoints
        in the source polygons. Each field gets a calculated variance,
        in the end the average of variances is being averaged and
        converted to a category.
        Returns  variance category <str>.
        """
        stepName = 'pointvarianceindex'

        def matrixToList(matrix, valueIndex):
            """
            Returns a list of all the values that appear in the field
            of the desired index.
            """
            outputList = []
            for areaProportion, rows in matrix:
                for row in rows:
                    outputList.append(row[valueIndex])
            return outputList


        # Categories and their maximum value:
        varianceCategories = [
            (30, "עומד הטרוגני מאוד"),
            (60, "עומד הטרוגני"),
            (100, "עומד אחיד")
        ]

        # Import all the data at once:
        # The order of the fields MUST NOT be changed 
        # without changing the indecies in the logic.
        totalFieldCodes = [40013, 40020, 40024, 40025, 40034, 40035, 40044, 40045 ,40114, 40119]#@, 40115]
        matrix = self.getMatrix_related('sp', totalFieldCodes)

        # varianceList - a list of field variance values,
        # to be averaged later.
        varianceList = []

        # VALIDATION:
        # Number of points must be > 1
        n_points = len(matrixToList(matrix,0))
        if n_points <= 1:
            # two origin polygon must include at least two seker points,
            # one for each polygon.
            txt = 'number of sekerpoints in both polygons is <= 1.'
            self.notifier.add(stepName, 'warning', txt)
            return None

        # LOGIC:
        # Go through every field or group of fields and calculate the fielde variance:
        indicies_freeValues = [0, 2, 4, 6, 9]#@, 10]
        for fieldCodeIndex in indicies_freeValues:
            values = matrixToList(matrix, fieldCodeIndex)

            # replace '' with None:
            while '' in values:
                values[values.index('')] = None
            
            # find the most frequent value:
            frequentValue = freqSorted(values)[0]
            variance = values.count(frequentValue) / n_points
            varianceList.append(variance)
        
        indicies_coverValues = [3, 5, 7]
        for fieldCodeIndex in indicies_coverValues:
            values = matrixToList(matrix, fieldCodeIndex)

            # replace the next values with None
            valuesToGroup = [
                '',
                'אין',
                'זניח (3%-0%)',
                'פזור (10%-3%)'
            ]
            # replace with None:
            for valueToGroup in valuesToGroup:
                while valueToGroup in values:
                    values[values.index(valueToGroup)] = None
            
            # find the most frequent value:
            frequentValue = freqSorted(values)[0]
            variance = values.count(frequentValue) / n_points
            varianceList.append(variance)

        # general density field index:
        index_generaldensity = 1
        values = matrixToList(matrix, index_generaldensity)
        # replace the next values with None
        valuesToGroup = [
            '',
            'אין עצים',
            'לא רלוונטי',
        ]
        # replace with None:
        for valueToGroup in valuesToGroup:
            while valueToGroup in values:
                values[values.index(valueToGroup)] = None
        # find the most frequent value:
        frequentValue = freqSorted(values)[0]
        variance = values.count(frequentValue) / n_points
        varianceList.append(variance)

        # treeharm field index:
        index_treeharm = 8
        values = matrixToList(matrix, index_treeharm)
        # replace the next values with None
        valuesToGroup = [
            '',
            'אין',
            'זניח (3%-0%)',
            'מועט (10%-3%)'
        ]
        # replace with None:
        for valueToGroup in valuesToGroup:
            while valueToGroup in values:
                values[values.index(valueToGroup)] = None
        # find the most frequent value:
        frequentValue = freqSorted(values)[0]
        variance = values.count(frequentValue) / n_points
        varianceList.append(variance)

        # done collecting fields' variance values.
        varianceAverage = average(varianceList)
        # multiply the variance average by 100 to convert to percentage.
        category = toCategory(varianceAverage * 100, varianceCategories)

        return category

#PROCESS
arcpy.env.overwriteOutput = True
org = Organizer(
    input_stands,
    input_unitelines,
    stands_tables_relationships
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

# 0.1 Check all the input fields exist (excel column checkIfExists)
#A1) First check fields of stands:
fieldsToCheck = [x for x in fieldsDict.values() if hasattr(x,'code')]
missingFields = []

fieldsToCheck_stands = [x for x in fieldsToCheck if str(x.code)[:2] == '50' and x.checkIfExists]
fieldnames_stands = [f.name.lower() for f in org.stands.desc.fields]
for smallFieldObj in fieldsToCheck_stands:
    name = smallFieldObj.name.lower()
    if name not in fieldnames_stands:
        missingFields.append(smallFieldObj)


#B) Check fields of stands' related tables:
fieldsToCheck_relted_tables = [x for x in fieldsToCheck if str(x.code)[:2] == '59' and x.checkIfExists]
for relationshipClass in org.stands.relationships.values():
    destination = relationshipClass.destination
    prefix = str(destination.fieldCodesPrefix)
    if destination.desc.datasetType != 'Table':
        continue
    fieldsToCheck_relatedTable_specific = [x for x in fieldsToCheck if str(x.code)[:2] == prefix and x.checkIfExists]
    fieldsToCheck_relatedTable = fieldsToCheck_relted_tables + fieldsToCheck_relatedTable_specific
    fieldnames_relatedTable = [f.name.lower() for f in destination.desc.fields]
    for smallFieldObj in fieldsToCheck_relatedTable:
        name = smallFieldObj.name.lower()
        if name not in fieldnames_relatedTable:
            missingFields.append(smallFieldObj)

#C) Check fiels of stands' related sekerpoints:
fieldsToCheck_relted_points = [x for x in fieldsToCheck if str(x.code)[:2] == '40' and x.checkIfExists]
destination = org.relationships['sp'].destination
fieldnames_relted_points = [f.name.lower() for f in destination.desc.fields]
for smallFieldObj in fieldsToCheck_relted_points:
        name = smallFieldObj.name.lower()
        if name not in fieldnames_relted_points:
            missingFields.append(smallFieldObj)


#D) Raise an ERROR if fields are missing:
#   e.g - CRASH the code here.
if missingFields:
    errorMessage = "One or more required fields are missing:"
    fieldsMessage = '\n'.join([fieldObj.asText() for fieldObj in missingFields])
    errorText = errorMessage + "\n" + fieldsMessage
    arcpy.AddError(errorText)

del smallFieldObj, fieldsToCheck_relatedTable, fieldsToCheck_relted_tables, fieldsToCheck_relatedTable_specific, fieldsToCheck_relted_points, destination

#### Process section 1: ####
#A) Delete product polygons of previous calculation.
arcpy.AddMessage('Deleting previous product stands and their related rows.')
orig_field = fieldsDict[unitelines_stands_relationship['originKey_code']].name
orig_field_exists = orig_field.lower() in [f.name.lower() for f in org.unitelines.desc.fields]
dest_field = fieldsDict[unitelines_stands_relationship['destinationKey_code']].name
dest_field_exists = dest_field.lower() in [f.name.lower() for f in org.stands.desc.fields]
stand_Keys = []
if orig_field_exists and dest_field_exists:
    # get all destination values:
    with arcpy.da.SearchCursor(org.unitelines.fullPath, [orig_field]) as sc:
        for r in sc:
            if r[0] is not None:
                stand_Keys.append(r[0])
    # create a definition query for stands and delete rows.
    # include (area = 0) for stands that didn't finish process (empty).
    sql_expression = 'shape_area = 0'
    if stand_Keys:
        sql_expression += ' OR %s IN (%s)' % (dest_field, ','.join([f"'{key}'" for key in stand_Keys]))
    with arcpy.da.UpdateCursor(org.stands.fullPath, [dest_field], where_clause=sql_expression) as uc:
        for r in uc:
            stand_Key = r[0]
            if stand_Key not in stand_Keys:
                stand_Keys.append(stand_Key)
            arcpy.AddMessage("~~~~~deleting polygon: %s~~~~~" % stand_Key)
            uc.deleteRow()

#B) Delete rows of product polygons' related tables.
if stand_Keys:
    for relationshipClass in org.relationships.values():
        if relationshipClass.destination.desc.dataType != 'Table':
            continue
        dest_field = relationshipClass.foreignKey_fieldName
        sql_expression = '%s IN (%s)' % (dest_field, ','.join([f"'{key}'" for key in stand_Keys]))
        with arcpy.da.UpdateCursor(relationshipClass.destination.fullPath, [dest_field], where_clause=sql_expression) as uc:
            for r in uc:
                uc.deleteRow()



#### Process section 2: ####
# Create fields in unite lines
# Find the relevant fields, based on 'toAdd' attribute:
fieldsToHandle = set()
for sf in fieldsDict.values():
    #Not all values have these attributes.
    if hasattr(sf,'toAdd') and hasattr(sf,'code'):
        #Checks: 1)need to add, and 2)belongs to 'lines':
        if sf.toAdd and str(sf.code)[:2] == '60':
            fieldsToHandle.add(sf)
#sort fieldsToHandle by sequence:
fieldsToHandle = list(fieldsToHandle)
fieldsToHandle.sort(key = lambda x: (x.sequence, x.code))

# one of the fields might be used by relationship class.
# if it does - delete the relationship class.
# this part was created in order to avoid errors
# that arise from deleting fields that are used by relationships.
relationship_name = "_".join([org.unitelines.name, org.stands.name])
relationship_fullPath = os.path.join(arcpy.env.workspace, relationship_name)
if arcpy.Exists(relationship_fullPath):
    desc = arcpy.Describe(relationship_fullPath)
    if desc.dataType == 'RelationshipClass':
        if fieldsDict[60002].name.lower() == desc.originClassKeys[0][0].lower():
            arcpy.management.Delete(relationship_fullPath)
    else:
        arcpy.management.Delete(relationship_fullPath)

#Notify in UI about process start:
message = 'Adding output fields to: %s.' % org.unitelines.name
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
        globalID_fieldObj = fieldsDict[60000]
        moveFieldToEnd(org.unitelines, smallFieldObj, globalID_fieldObj)
    elif smallFieldObj.toAdd == 'blank':
        createBlankField(org.unitelines, smallFieldObj)

    arcpy.SetProgressorPosition()
    counter += 1
del counter, tempMessage
arcpy.ResetProgressor()



#### Process section 3: ####
# relate unite lines with stands FCs:
# every unite line has a new polygon related to it.

#Notify in UI about process start:
message = 'Creating relationship class: unite lines → stands'
arcpy.SetProgressor("default",message)
arcpy.AddMessage(message)

"""
Nickname of the relationship, represents the relationship class and its
function in the code. Stays constant and independent of featureclasses'
or tables' names, so using it is favorable.
"""

# The fields of linkage: 
# from: unite lines, stand_id, 60002
# to:   stands,      GlobalID, 50024
originKey_name = fieldsDict[unitelines_stands_relationship['originKey_code']].name
destinationKey_name = fieldsDict[unitelines_stands_relationship['destinationKey_code']].name
nickname = unitelines_stands_relationship['nickname']
newRelationship_desc = createRelation(org.unitelines, originKey_name, org.stands, destinationKey_name)
relationshipClass = RelationshipClass(newRelationship_desc.name, nickname, org.unitelines)
org.relationships[nickname] = relationshipClass
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
# Go through each unite line:

#Notify in UI about process start:
message = 'Calculating...'
featureCount = getFeatureCount(org.unitelines.name)
arcpy.SetProgressor("step",message,0,featureCount,1)
arcpy.AddMessage(message)
counter = 1

# A list of UniteLine object, that are valid and were calculated:
calculatedJoints = []

uniteLines_uc = arcpy.UpdateCursor(
    org.unitelines.name,
    #where_clause = 'OBJECTID IN (67, 168, 331, 369, 268)', #for debug!!!
    sort_fields = "%s A" % org.unitelines.oidFieldName
    )
#Main iteration:
for uniteLines_r in uniteLines_uc:
    tempMessage = 'Calculating... (row: %s of %s feafures)' % (counter, featureCount)
    arcpy.SetProgressorLabel(tempMessage)

    standObj = UniteLine(uniteLines_r, org.unitelines)
    uniteLines_uc.updateRow(standObj.row)

    arcpy.SetProgressorPosition()
    counter += 1
del uniteLines_uc
