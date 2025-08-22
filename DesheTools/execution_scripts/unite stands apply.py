# -*- coding: utf-8 -*-
import os
import re
import arcpy
import math
from collections import Counter
import numpy as np

#TOOL PARAMETERS
debug_mode = True
if debug_mode:
    #debug parameters
    input_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\מרץ 2024\QA\22.7.2025 - apply\NirEtzion_1111_verification.gdb'
    input_stands = os.path.join(input_workspace, 'stands_1111_fnl')
    input_unitelines = os.path.join(input_workspace, 'הערותקוויותלדיוןשני_ExportFeatures')
    input_sekerpoints = os.path.join(input_workspace, 'smy_NirEtzion')
    #input_configurationFolder = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\Github - Deshe\Deshe\DesheTools\configuration'
    input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')
else:
    input_stands = arcpy.GetParameter(0)
    #Take all the features, even if layar has selection.
    input_stands = arcpy.Describe(input_stands).catalogPath
    
    input_unitelines = arcpy.GetParameter(1)
    #Take all the features, even if layar has selection.
    input_unitelines = arcpy.Describe(input_unitelines).catalogPath

    input_sekerpoints = arcpy.GetParameter(2)
    #Take all the features, even if layar has selection.
    input_sekerpoints = arcpy.Describe(input_sekerpoints).catalogPath

    input_configurationFolder = arcpy.GetParameterAsText(3)
    #input_configurationFolder = os.path.join(os.path.dirname(__file__), '..', 'configuration')


#VARIABLES
fieldsExcel = os.path.join(input_configurationFolder, 'fields.xlsx')
fieldsExcel_sheet = 'unite stands'
#GDB that contains all the domains needed.
origin_GDB = os.path.join(input_configurationFolder, 'origin.gdb')
origin_GDB_domains = arcpy.Describe(origin_GDB).domains
#Import JSON file

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
sekerpoints_tables_relationships = {
    #'nickname': ('name of relationship class', field codes prefix <int>),
    'pt1': (os.path.basename(input_sekerpoints) + '_InvasiveSpecies', 41),
    'pt2': (os.path.basename(input_sekerpoints) + '_PlantTypeCoverDistribut', 42),
    'pt3': (os.path.basename(input_sekerpoints) + '_StartRepeatDominTree', 43),
    'pt4': (os.path.basename(input_sekerpoints) + '_VitalForest', 44),
}

#Fields to be added to each related table
#the first one is ALWAYS used for linkage in relationship class!
#the order of the other codes matters as well.
#[stand_ID, standAddress, FOR_NO, HELKA, STAND_NO]
stands_relatedTables_globalFieldCodes = [59001,59002,59003,59004,59005]

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

def buildSqlQuery(featureClass, fieldName, value, mode = "=", wQuote = True):
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
    if wQuote:
        value = f"'{value}'"
    if mode in ("=", "<>"):
        return """{0} {1} {2}""".format(fieldName_delimited, mode, value)
    elif mode in ("= timestamp", "<> timestamp"):
        return """{0} {1} {2}""".format(fieldName_delimited, mode, value)
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

def getNewlyCreatedValue(fc, fieldName):
    """
    Returns the value of the fieldName of the last row created,
    sorted by the highest objectID.
    """
    maxID = 0
    outVal = None
    with arcpy.da.SearchCursor(fc, ['OID@', fieldName]) as sc:
        for r in sc:
            if r[0] > maxID:
                maxID = r[0]
                outVal = r[1]
    return outVal

def getMaxValue(fc, fieldName):
    """
    Returns the maximum value of the fieldName in the feature class.
    """
    maxVal = 0
    with arcpy.da.SearchCursor(fc, fieldName) as sc:
        for r in sc:
            if r[0] > maxVal:
                maxVal = r[0]
    return maxVal

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
    def __init__(self, stands, unitelines, sekerpoints, standsRelationships, sekerpointsRelationships):
        self.stands = FeatureClass(stands)
        self.unitelines = FeatureClass(unitelines)
        self.sekerpoints = FeatureClass(sekerpoints)
        arcpy.AddMessage('Organizer initialized with:\n- Stands: %s\n- Unitelines: %s\n- Seker points: %s' % (self.stands.fullPath, self.unitelines.fullPath, self.sekerpoints.fullPath))
        #Coordinate system of both FCs must be the same.
        self.checkSR([self.stands, self.unitelines, self.sekerpoints])
        if self.stands.workspace != self.unitelines.workspace:
            arcpy.AddError('Stands and seker points are not in the same workspace.')
        #@arcpy.env.workspace = self.stands.workspace
        arcpy.AddMessage('Workspace: %s' % self.stands.workspace)
        
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
        
        #Create and bind RelationshipClasses existing relationships between sekerpoints
        #and its related TABLES.
        for nickname, relTup in sekerpointsRelationships.items():
            #relTup = ('name of relationship class', field codes prefix <int>)
            relName = relTup[0]
            fieldCodesPrefix = relTup[1]
            #relationships <dict>: 'nickname': 'name of relationship class'.
            self.relationships[nickname] = RelationshipClass(relName, nickname, self.sekerpoints)
            #a patch to relationship's destination FC:
            #was made for verification of field existance.
            self.relationships[nickname].destination.fieldCodesPrefix = fieldCodesPrefix

        #Create and bind RelationshipClasses existing relationships between stand
        #and its related UNITELINES.
        relName = unitelines_stands_relationship['name']
        nickname = unitelines_stands_relationship['nickname']
        self.relationships[nickname] = RelationshipClass(relName, nickname, self.unitelines)

        #Create and bind RelationshipClasses existing relationships between stand
        #and its related POINTS.
        #Find the relationship between current stands and points:
        relDesc = self.getRelationshipToSekerpoints()
        relName = relDesc.name
        nickname = 'sp'
        self.relationships[nickname] = RelationshipClass(relName, nickname, self.stands)

        #References of corresponding organizer objects:
        #to be populated later.
        self.buckupOrganizer = None
        self.buckupOfOrganizer = None
        
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
            relDesc = arcpy.Describe(os.path.join(self.stands.workspace, relationshipName))
            destDesc = arcpy.Describe(os.path.join(self.stands.workspace, relDesc.destinationClassNames[0]))
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
        return 'Organizer object. workspace: %s' % self.stands.workspace

    def initBuckupDatabase(self):
        """
        Identifies a buckup database based on the suffix added to the current database.
        """
        buckupDatabase_suffix = '_buckup'
        #Get the current database:
        currentDatabase = self.stands.workspace
        #Get buckup database path:
        buckupDatabase = currentDatabase.replace('.gdb', buckupDatabase_suffix + '.gdb')
        buckupDatabase_basename = os.path.basename(buckupDatabase)
        #Check if the buckup database exists:
        if not arcpy.Exists(buckupDatabase):
            buckupDatabase_existed = False
            #Create the buckup database from the current database scheme:
            arcpy.AddMessage('Creating a buckup database: %s' % buckupDatabase_basename)
            folderPath = os.path.dirname(currentDatabase)
            arcpy.management.CreateFileGDB(folderPath, buckupDatabase_basename)
            # create a scheme file
            schemeFile = os.path.join(folderPath, 'scheme.xml')
            arcpy.management.ExportXMLWorkspaceDocument(
                currentDatabase,
                schemeFile,
                export_type="SCHEMA_ONLY"
            )
            # import the scheme file to the buckup database
            arcpy.management.ImportXMLWorkspaceDocument(
                buckupDatabase,
                schemeFile,
                import_type="SCHEMA_ONLY",
            )
            arcpy.management.Delete(schemeFile)
        else:
            buckupDatabase_existed = True
            arcpy.AddMessage('Existing buckup database identified: %s' % buckupDatabase_basename)
            #@PATCH_TEMPORARY_7.25 - did not validate the existing buckup database scheme

        return buckupDatabase

    def replicate(self):
        """
        Creates a new Organizer object that is a replica of the current one,
        but with paths modified to point to the buckup database.
        * "bu" = backup.
        """
        # Modify paths to point to the buckup database:
        bu_input_stands = self.stands.fullPath.replace('.gdb', '_buckup.gdb')
        bu_input_unitelines = self.unitelines.fullPath.replace('.gdb', '_buckup.gdb')
        bu_input_sekerpoints = self.sekerpoints.fullPath.replace('.gdb', '_buckup.gdb')
        
        arcpy.AddMessage(f'bu_stands: {bu_input_stands}')
        arcpy.AddMessage(f'bu_unitelines: {bu_input_unitelines}')
        arcpy.AddMessage(f'bu_sekerpoints: {bu_input_sekerpoints}')

        newOrg = Organizer(
            bu_input_stands,
            bu_input_unitelines,
            bu_input_sekerpoints,
            stands_tables_relationships,
            sekerpoints_tables_relationships
        )
        # Create references between organizers:
        self.buckupOrganizer = newOrg
        newOrg.buckupOfOrganizer = self
        arcpy.AddMessage(f'organizer created in workspace: {newOrg.__repr__()}')
        return newOrg

class RelationshipClass:
    def __init__(self, relationshipName, nickname, originFC):
        self.desc = arcpy.Describe(os.path.join(originFC.workspace, relationshipName))
        self.name = self.desc.name
        self.nickname = nickname
        self.fullPath = self.desc.catalogPath
        self.workspace = self.desc.path
        #Check that originFC == relationship class' origin FC:
        if originFC.fullPath !=  os.path.join(self.desc.path, self.desc.originClassNames[0]):
            arcpy.AddError("Origin FCs don't match between sekerpoints and relationship provided.")
        self.origin = originFC
        #Create a pointer to the destination FC here:
        self.destination = FeatureClass(os.path.join(self.desc.path, self.desc.destinationClassNames[0]))
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
        arcpy.AddMessage('Started handling: uniteLine %s = %s'% (self.FC.oidFieldName, self.id))
        #@PATCH_TEMPORARY_7.25 - disable notifications
        #self.notifier = Notifier(self, 60005)

        self.joint_isValid = self.getSelfValue(60003) == 'תקין' and self.getSelfValue(60002)

        if self.joint_isValid:
            # Act according to descision value:
            descision = self.getSelfValue(60006)
            if descision == '1':
                # Desicion is '1' - approved for merge
                # 1) Copy line's origin stands and related tables
                # from current database to the buckup database.
                # 2) Delete origin stands and their related tables. 
                # 3) Update the line's origin stands guid to the 
                # new guid from the buckup database.
                # 4) Update the line's status to 0 - ממתין להחלטה.
                # 5) Annex sekerpoints to the new stands.

                # copy stand to the backup database
                # and update the line's origin stands guid to the new guid
                # from the buckup database.
                orig_relationship_ls = self.FC.relationships['ls']
                orig_FC = orig_relationship_ls.destination
                fieldNames = [field.name for field in orig_FC.desc.fields]
                buckup_relationship_ls = org_buckup.relationships['ls']
                buckup_FC = buckup_relationship_ls.destination
                # replace shape field with "SHAPE@"
                for i, fieldName in enumerate(fieldNames):
                    if fieldName.lower() == 'shape':
                        fieldNames[i] = 'SHAPE@'
                standIDs_old = self.getSelfValue([60007, 60008])
                standIDs_new = ['', '']
                standID_product = self.getSelfValue(60002)
                for i, standID in enumerate(standIDs_old):
                    sqlQuery = buildSqlQuery(orig_FC.fullPath,
                                             orig_relationship_ls.foreignKey_fieldName,
                                             standID)
                    
                    orig_uc = arcpy.da.UpdateCursor(orig_FC.fullPath, fieldNames, where_clause = sqlQuery)
                    buckup_ic = arcpy.da.InsertCursor(buckup_FC.fullPath, fieldNames)
                    for orig_r in orig_uc:
                        # insert row to the buckup gdb and collect the globalID
                        buckupObjectid = buckup_ic.insertRow(orig_r)
                        # delete the original stand row
                        orig_uc.deleteRow()
                    del buckup_ic, orig_uc
                    if 'orig_r' in locals(): del orig_r
                    # get the new guid
                    buckup_sqlQuery = f'{buckup_relationship_ls.destination.oidFieldName} = {buckupObjectid}'
                    buckup_sc = arcpy.da.SearchCursor(buckup_FC.fullPath, buckup_relationship_ls.foreignKey_fieldName, where_clause = buckup_sqlQuery)
                    for buckup_r in buckup_sc:
                        standIDs_new[i] = buckup_r[0]
                    del buckup_sc
                    
                    
                    # copy stands' rows from related tables
                    # to the buckup database.
                    for nickname in stands_tables_relationships.keys():
                        # stX - st1, st2, st3, st4
                        orig_relationship_stX = org.relationships[nickname]
                        orig_tableX = orig_relationship_stX.destination
                        buckup_relationship_stX = org_buckup.relationships[nickname]
                        buckup_tableX = buckup_relationship_stX.destination
                        
                        # locate foreignKey_fieldName ('stand_id') field index:
                        fieldNames_table = [field.name for field in orig_tableX.desc.fields]
                        foreignKey_index = [i for i, field in enumerate(fieldNames_table) if field.lower() == orig_relationship_stX.foreignKey_fieldName.lower()][0]
                        sqlQuery = buildSqlQuery(orig_tableX.fullPath,
                                                 orig_relationship_stX.foreignKey_fieldName,
                                                 standID)
                        orig_uc = arcpy.da.UpdateCursor(orig_tableX.fullPath, fieldNames_table, where_clause = sqlQuery)
                        buckup_ic = arcpy.da.InsertCursor(buckup_tableX.fullPath, fieldNames_table)
                        for orig_r in orig_uc:
                            # replace the foreignKey field value with the new guid
                            orig_r = list(orig_r)
                            orig_r[foreignKey_index] = standIDs_new[i]
                            # insert row to the buckup gdb
                            buckup_ic.insertRow(tuple(orig_r))
                            # delete the original table row
                            orig_uc.deleteRow()
                        del orig_uc, buckup_ic
                    
                    # assign sekerpoints to the new stand
                    orig_relationship_sp = org.relationships['sp']
                    orig_sekerpointsFC = orig_relationship_sp.destination
                    sekerpoints_sqlQuery = buildSqlQuery(orig_sekerpointsFC.fullPath,
                                                         orig_relationship_sp.foreignKey_fieldName,
                                                         standID)
                    orig_sekerpoints_uc = arcpy.UpdateCursor(orig_sekerpointsFC.fullPath,
                                                 where_clause = sekerpoints_sqlQuery)
                    for orig_sekerpoints_r in orig_sekerpoints_uc:
                        # replace the foreignKey field value with the new guid
                        orig_sekerpoints_r.setValue(orig_relationship_sp.foreignKey_fieldName, standID_product)
                        orig_sekerpoints_uc.updateRow(orig_sekerpoints_r)
                    del orig_sekerpoints_uc

                # update the line's origin stands guid to the new guid
                # from the buckup database.
                # update the line's status to None (null).
                self.writeSelf([60006, 60007, 60008], [None] + standIDs_new)

            elif descision == '2':
                # Desicion is '2' - restore from buckup.
                #@PATCH_TEMPORARY_7.25
                pass

            else:
                arcpy.AddMessage('UniteLine descision is not 1 or 2, no action taken.')

    def getStands(self, standsFC):
        """
        Finds stands that contain this unite line start-, and end-points.
        Returns a list of StandPolygons.
        """
        stands = []
        uniteLine_shape = self.getSelfValue(60001)
        try:
            unitePoints = [uniteLine_shape.firstPoint, uniteLine_shape.lastPoint]
        except:
            # unable to get first and last points of the line.
            return stands
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

class StandPolygon(FcRow):
    def __init__(self, parentFcRow, row, sekerpointsFC):
        FcRow.__init__(self, row, sekerpointsFC)
        self.parent = parentFcRow
        self.notifier = self.parent.notifier

        self.selfData = {}
        self.relatedData = {}
        self.acquireData()

        self.area = self.getSelfData(50001).area
        self.globalID = self.getSelfData(50024)

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

#PROCESS
arcpy.env.overwriteOutput = True
org = Organizer(
    input_stands,
    input_unitelines,
    input_sekerpoints,
    stands_tables_relationships, 
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

#### Process section 0: ####
# Check fields exist and notify if not.
#@PATCH_TEMPORARY_7.25 - does not check fields
"""
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
"""

#### Process section 1: ####
# Initiate buck-up database:
# If it exists - identify it with a new Organizer object,
# if not - create a new, empty one, based on the input database scheme.
"""
message = 'Creating a buck-up database...'
arcpy.AddMessage(message)
arcpy.SetProgressor("default",message)and
"""
org.initBuckupDatabase()

# Create a new Organizer object for the buck-up database:
org_buckup = org.replicate()

#### Process section 2: ####
# Check for .lock files in the databases:
lock_pattern = re.compile(r".*\.lock$")
for organizerInspected in [org, org_buckup]:
    inspectedDatasets = set()
    for relationship in organizerInspected.relationships.values():
        inspectedDatasets.add(relationship.destination.fullPath)
        inspectedDatasets.add(relationship.origin.fullPath)
    for i in inspectedDatasets:
        try:
            if not arcpy.TestSchemaLock(i):
                error_message = f"dataset {i} has a schema lock."
                raise arcpy.ExecuteError(error_message)
        except arcpy.ExecuteError:
            arcpy.AddError("Script aborted due to active geodatabase locks.")
            # You might want to exit more forcefully if not in a script tool context
            # import sys
            # sys.exit(1)
            raise # Re-raise the error to propagate it and stop the script tool execution
        except Exception as e:
            # Catch any other unexpected errors during the lock file check
            arcpy.AddError(f"An unexpected error occurred during lock check: {e}")
            raise # Re-raise to stop the script tool execution

#### Process section 3: ####
# Go through each unite line:

# Check for existing locks:
# Collect all datasets that are inspected for locks:
# This includes both the original and the buck-up databases.
inspectedDatasets = set()
for organizerInspected in [org, org_buckup]:
    for relationship in organizerInspected.relationships.values():
        inspectedDatasets.add(relationship.destination.fullPath)
        inspectedDatasets.add(relationship.origin.fullPath)
inspectedDatasets = list(inspectedDatasets)
inspectedDatasets_locks = [i for i in inspectedDatasets if not arcpy.TestSchemaLock(i)]
try:
    if inspectedDatasets_locks:
        inspectedDatasets_locks_desc = [arcpy.Describe(i) for i in inspectedDatasets_locks]
        messages = [f'gdb: {d.workspace.name} - dataset: {d.name}.' for d in inspectedDatasets_locks_desc]
        error_message = f"The following datasets have a schema lock:\n" + "\n\t".join(messages)
        raise arcpy.ExecuteError(error_message)
    else:
        arcpy.AddMessage(f"Did not find schema locks.")
        # Get a list of Unite Lines object IDs:
        uniteLines_OIDs = []
        with arcpy.da.SearchCursor(
            org.unitelines.fullPath,
            [org.unitelines.oidFieldName],
            where_clause='OBJECTID IS NOT NULL'
        ) as oid_cursor:
            for row in oid_cursor:
                uniteLines_OIDs.append(row[0])
except arcpy.ExecuteError:
    arcpy.AddError("Script aborted due to geodatabase access issues.")
    # No need to stopEditing here; the 'with' statement for editor handles it.
    raise # Re-raise to signal failure to the geoprocessing framework

# Notify in UI about process start:
message = 'Processing Unite Lines...'
featureCount = len(uniteLines_OIDs)
arcpy.SetProgressor("step",message,0,featureCount,1)
arcpy.AddMessage(message)

# --- Start editing the geodatabase: ---

try:
    for lineOID in uniteLines_OIDs:
        arcpy.SetProgressorPosition()
        counter = uniteLines_OIDs.index(lineOID)+1
        arcpy.AddMessage(f"Processing Unite Line: {counter} of {featureCount}")
        # Create an SearchCursor for the Unite Lines feature class,
        # gather the necessary fields, and terminate the cursor.
        unitelines_fieldCodes = [60002, 60003, 60006, 60007, 60008]
        unitelines_fieldNames = [fieldsDict[code].name for code in unitelines_fieldCodes]
        unitelines_sqlQuery = buildSqlQuery(org.unitelines.fullPath, org.unitelines.oidFieldName, lineOID, wQuote = False)
        with arcpy.da.SearchCursor(
            org.unitelines.fullPath,
            unitelines_fieldNames,
            where_clause=unitelines_sqlQuery
        ) as unitelines_sc:
            for unitelines_row in unitelines_sc:
                # a dict that coordinates between field codes and their values:
                uniteline_fieldValues = {code: unitelines_row[i] for i, code in enumerate(unitelines_fieldCodes)}
        # valid joint condition:
        # stats is 'תקין' and product stand_id is not None.
        joint_isValid = uniteline_fieldValues[60003] == 'תקין' and uniteline_fieldValues[60002]
        if not joint_isValid:
            # If the joint is not valid, skip this row.
            arcpy.AddMessage(f"Skipping Unite Line OID: {lineOID} - Joint is not valid. Check unite line's status or stand id.")
            continue
        # Joint is valid.
        # Act according to descision value:
        descision = uniteline_fieldValues[60006]
        if descision == '1':
            # copy stand to the backup database
            # and update the line's origin stands guid to the new guid
            # from the buckup database.
            orig_relationship_ls = org.unitelines.relationships['ls']
            orig_FC = orig_relationship_ls.destination
            buckup_relationship_ls = org_buckup.relationships['ls']
            buckup_FC = buckup_relationship_ls.destination
            standIDs_old = [uniteline_fieldValues[60007], uniteline_fieldValues[60008]]
            standIDs_new = ['', '']
            standID_product = uniteline_fieldValues[60002]
            for i, standID in enumerate(standIDs_old):
                origStand_sqlQuery = buildSqlQuery(orig_FC.fullPath,
                                                    orig_relationship_ls.foreignKey_fieldName,
                                                    standID)
                # Move stand to row buckup gdb:
                arcpy.AddMessage(f'orig_FC: {orig_FC.fullPath}')
                arcpy.AddMessage(f'buckup_FC: {buckup_FC.fullPath}')
                arcpy.management.Append(orig_FC.fullPath, buckup_FC.fullPath, schema_type='TEST', expression=origStand_sqlQuery)
                # Get the new stand's objectid and globalID:
                buckup_standID_new = getNewlyCreatedValue(buckup_FC.fullPath, buckup_relationship_ls.foreignKey_fieldName)
                standIDs_new[i] = buckup_standID_new
                
                """
                # CUT-PASTE stand's rows of related tables:
                for nickname in stands_tables_relationships.keys():
                    # stX - st1, st2, st3, st4
                    orig_relationship_stX = org.relationships[nickname]
                    orig_tableX = orig_relationship_stX.destination
                    buckup_relationship_stX = org_buckup.relationships[nickname]
                    buckup_tableX = buckup_relationship_stX.destination
                    
                    # locate foreignKey_fieldName ('stand_id') field index:
                    fieldNames_table = [field.name for field in orig_tableX.desc.fields]
                    foreignKey_index = [i for i, field in enumerate(fieldNames_table) if field.lower() == orig_relationship_stX.foreignKey_fieldName.lower()][0]
                    sqlQuery = buildSqlQuery(orig_tableX.fullPath,
                                                orig_relationship_stX.foreignKey_fieldName,
                                                standID)
                    with arcpy.da.UpdateCursor(orig_tableX.fullPath, fieldNames_table, sqlQuery) as orig_uc:
                        with arcpy.da.InsertCursor(buckup_tableX.fullPath, fieldNames_table) as buckup_ic:
                            for orig_r in orig_uc:
                                # replace the foreignKey field value with the new guid
                                orig_r = list(orig_r)
                                orig_r[foreignKey_index] = standIDs_new[i]
                                # insert row to the buckup gdb
                                buckup_ic.insertRow(tuple(orig_r))
                                arcpy.AddMessage('added row to buckup gdb - related table: %s' % orig_tableX.name)
                                # delete the original table row
                                orig_uc.deleteRow()
                                arcpy.AddMessage('deleted row from original gdb - related table: %s' % orig_tableX.name)

                # ASSAIN sekerpoints to the new buckup stand:
                orig_relationship_sp = org.relationships['sp']
                orig_sekerpointsFC = orig_relationship_sp.destination
                sekerpoints_sqlQuery = buildSqlQuery(orig_sekerpointsFC.fullPath, orig_relationship_sp.foreignKey_fieldName, standID)
                with arcpy.da.UpdateCursor(orig_sekerpointsFC.fullPath, orig_relationship_sp.foreignKey_fieldName, sekerpoints_sqlQuery) as orig_sekerpoints_uc:
                    for orig_sekerpoints_r in orig_sekerpoints_uc:
                        # replace the foreignKey field value with the new guid
                        orig_sekerpoints_r[0] = standID_product
                        orig_sekerpoints_uc.updateRow(orig_sekerpoints_r)
                        arcpy.AddMessage('updated sekerpoint to buckup stand - sekerpoint: %s' % orig_sekerpoints_r[0])

                # DELETE stand from the original database:
                arcpy.AddMessage('Deleting original stand: %s' % origStand_sqlQuery)
                with arcpy.da.UpdateCursor(orig_FC.fullPath, fieldNames, where_clause = origStand_sqlQuery) as orig_uc:
                    for orig_r in orig_uc:
                        orig_uc.deleteRow()
                        arcpy.AddMessage('~deleted~')
                """
            # UPDATE unite line with backup stand IDs:
            """
            unitelines_fieldNames = [fieldsDict[60007].name, fieldsDict[60008].name, fieldsDict[60006].name]
            with arcpy.da.UpdateCursor(org.unitelines.fullPath, unitelines_fieldNames, unitelines_sqlQuery) as unitelines_uc:
                for unitelines_r in unitelines_uc:
                    # update the row with the new buckup stand IDs
                    unitelines_r[0] = standIDs_new[0]
                    unitelines_r[1] = standIDs_new[1]
                    unitelines_uc.updateRow(unitelines_r)
                    # update the line's status to None (null)
                    unitelines_r[2] = None
                    arcpy.AddMessage('updated unite line with new buckup stand IDs')
            """

except arcpy.ExecuteError:
    arcpy.AddError("Script aborted due to an ArcPy execution error.")
    raise
except Exception as e:
    arcpy.AddError(f"An unexpected Python error occurred: {e}")
    raise

#arcpy.ClearWorkspaceCache_management(org.unitelines.workspace)
#arcpy.ClearWorkspaceCache_management(org_buckup.unitelines.workspace)

arcpy.AddMessage("Script finished.")




"""
uniteLines_uc = arcpy.UpdateCursor(
    org.unitelines.fullPath,
    #where_clause = 'OBJECTID = 1', #for debug!!!
    sort_fields = "%s A" % org.unitelines.oidFieldName
    )
#Main iteration:
for uniteLines_r in uniteLines_uc:
    arcpy.SetProgressorLabel(tempMessage)

    lineObj = UniteLine(uniteLines_r, org.unitelines)
    uniteLines_uc.updateRow(lineObj.row)

    arcpy.SetProgressorPosition()
del uniteLines_uc
"""