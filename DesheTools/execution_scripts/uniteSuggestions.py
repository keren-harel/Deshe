# -*- coding: utf-8 -*-
import os, arcpy, datetime

#VARIABLES
symbologyLyrx = r"Z:\Other_Org\KKL\DilulForest\AutomationTools\PreMappingCode\january2022\suggestions.lyrx"
working_GDB = 'in_memory'
#working_GDB = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\נובמבר 2021\november 21\inMemo.gdb'
input_FC = arcpy.GetParameter(0)
input_FC = arcpy.Describe(input_FC).catalogPath
sr = arcpy.Describe(input_FC).spatialReference
links_table = os.path.join(working_GDB, "links")
infoFields = ["HELKA", "STAND_NO"]
#suffix as numbers:
infoFields_suffix = [1, 2]
#output:
outputFC = arcpy.GetParameter(1)
#suggestions_workspace = r'C:\Users\Dedi\Desktop\עבודה\My GIS\דשא\נובמבר 2021\november 21\outputs.gdb'
suggestions_workspace = arcpy.Describe(outputFC).path
#suggestions_FCName = 'suggestions1'
suggestions_FCName = arcpy.Describe(outputFC).basename
#suggestions_FC = os.path.join(suggestions_workspace, suggestions_FCName)
suggestions_FC = arcpy.Describe(outputFC).catalogPath

fields = {"feature1": {"name" : "feature1",
                         "alias" : "ישות 1",
                         "type" : "SHORT",
                         "length" : "120"},
          "feature2": {"name" : "feature2",
                                  "alias" : "ישות 2",
                                  "type" : "SHORT",
                                  "length" : "120"},
          "notes": {"name" : "notes",
                                 "alias" : "הערות",
                                 "type" : "TEXT",
                                 "length" : "1000"},
        }

#fieldOI_3 = "MainForestLayerVegForm2"
fieldOI_3 = "CoverTypeName"
fieldOI_4 = "ageCategory"
#HORESH / SIHIA / BATA / ESBONI.
fieldOI_2 = fieldOI_3
fieldOI_2_sizeExceptions = [
    "חורש",
    "שיחייה",
    "בתה",
    "עשבוני"
]

#fields to check for existance:
requiredFields = [fieldOI_2, fieldOI_3, fieldOI_4] + infoFields

note_1 = "שטח קטן"
note_2 = "תצורת צומח וקבוצת גיל זהה"

#FUNCTIONS
def fieldDictFromName(FC, name, suffix):
    LF = arcpy.ListFields(FC, name)
    F = LF[0]
    F.name = F.name + suffix
    F.aliasName = F.aliasName + suffix
    outDict = {
        "name": F.name,
        "alias": F.aliasName,
        "length": F.length,
        "type": F.type
    }
    return outDict

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
def getOidFieldName(fc):
    #returns the Objectid field of a fc.
    fc_desc = arcpy.Describe(fc)
    oidFieldName = fc_desc.oidFieldName
    del fc_desc
    return oidFieldName

def getIntersection(shape1, shape2):

    '''
    #arrow from centroid to centroid:
    ar = arcpy.Array()
    ar.add(p1.shape.centroid)
    ar.add(p2.shape.centroid)
    polyline = arcpy.Polyline(ar, sr)
    '''
    #first: get line of touch (2):
    intersection = shape1.intersect(shape2, 2)
    if intersection.length > 0:
        return intersection
    #second: get area of overlap as boundary:
    intersection = shape1.intersect(shape2, 4).boundary()
    if intersection.length > 0:
        return intersection
    #third: if there is a point of touch:
    #make a buffer around the point as a line, clip by relevant polygons:
    bufferLine = shape1.intersect(shape2, 1).buffer(8).boundary()
    dissolved = shape1.union(shape2)
    intersection = bufferLine.intersect(dissolved, 2)
    return intersection

def fieldNameFromPrefix(fc, prefix):
    #returns a full field name for a given prefix.
    fields = arcpy.ListFields(fc)
    for fieldName in [f.name for f in fields ]:
        if fieldName.startswith(prefix): return fieldName

#CLASSES
class Polygon:
    def __init__(self, row, objectid_FieldName):
        self.id = row.getValue(objectid_FieldName)
        self.shape = row.getValue('shape')
        self.info = {}
        for infoField in infoFields:
            self.info[infoField] = row.getValue(infoField)
        if self.shape is not None:
            #Area in DUNAM
            self.area = self.shape.getArea('GEODESIC', 'SQUAREMETERS') / 1000.0
            isSizeException = row.getValue(fieldOI_2) in fieldOI_2_sizeExceptions
            self.areaIsSmall = False
            if self.area <= 10 + 40*int(isSizeException):
                self.areaIsSmall = True
        self.fieldvalue_3 = row.getValue(fieldOI_3)
        self.fieldvalue_4 = row.getValue(fieldOI_4)
        self.neighbors = []

class Link:
    def __init__(self, row):
        objectIDs = [row.getValue(sourceFieldName), row.getValue(neighborFieldName)]
        self.features = [polygons[ID] for ID in objectIDs]
        #sort by area from smallest to largest:
        self.features.sort(key=lambda x: x.area, reverse=False)
        #two conditions:
        #cond_1 (section 2) - at least one ieature:
        #area <= 10 (or 50 if it's HORESH / SIHIA / BATA / ESBONI).
        self.cond_1 = self.features[0].areaIsSmall or self.features[1].areaIsSmall
        #cond_2 (sections 3 and 4) - both field are identical in both features.
        cond_2a = self.features[0].fieldvalue_3 == self.features[1].fieldvalue_3
        cond_2b = self.features[0].fieldvalue_4 == self.features[1].fieldvalue_4
        self.cond_2 = cond_2a and cond_2b
        
        self.cond_3 = self.features[0].info["HELKA"] == self.features[1].info["HELKA"]
        #associate the features:
        self.features[0].neighbors.append(self.features[1])
        self.features[1].neighbors.append(self.features[0])



#PROCESS
for field in requiredFields:
    if not fieldExists(input_FC, field):
        arcpy.AddError("Field does't exist:\n-field name: %s" % field)

oid = getOidFieldName(input_FC)
polygons = {}
links = []

sc = arcpy.SearchCursor(input_FC)
for r in sc:
    polygon = Polygon(r, oid)
    polygons[polygon.id] = polygon
del sc

arcpy.analysis.PolygonNeighbors(input_FC, links_table, both_sides = False)
#find the field name for source_objectid and neighbor_objectid:
#because it might change unpredictably.
#for now i can find it by a fixed prefix.
sourceFieldName = fieldNameFromPrefix(links_table, "src")
neighborFieldName = fieldNameFromPrefix(links_table, "nbr")
sc = arcpy.SearchCursor(links_table)
arcpy.AddMessage(links_table)
for r in sc:
    link = Link(r)
    links.append(link)
del sc

if len(links) > 0:
    counter = 0
    hasZeroLengthFeatures = False
    #create feature
    arcpy.management.CreateFeatureclass(suggestions_workspace,
                                        suggestions_FCName,
                                        "POLYLINE",
                                        spatial_reference = sr)
    createBlankField(suggestions_FC, fields["feature1"])
    createBlankField(suggestions_FC, fields["feature2"])
    createBlankField(suggestions_FC, fields["notes"])
    for infoField in infoFields:
        for suffix in infoFields_suffix:
            fName = infoField + str(suffix)
            createBlankField(suggestions_FC,
                             fieldDictFromName(input_FC, infoField, str(suffix)))
    ic = arcpy.InsertCursor(suggestions_FC)
    for link in links:
        if (link.cond_1 or link.cond_2) and link.cond_3:
            counter += 1
            r = ic.newRow()
            p1 = link.features[0]
            p2 = link.features[1]
            polyline = getIntersection(p1.shape, p2.shape)
            r.setValue('shape', polyline)
            r.setValue(fields["feature1"]["name"], p1.id)
            r.setValue(fields["feature2"]["name"], p2.id)
            for infoField in infoFields:
                r.setValue(infoField + str(1), p1.info[infoField])
                r.setValue(infoField + str(2), p2.info[infoField])
            #comment:
            notes = []
            if link.cond_1:
                notes.append(note_1)
            if link.cond_2:
                notes.append(note_2)
            notes_text = "\n".join(["-"+x for x in notes])
            r.setValue(fields["notes"]["name"], notes_text)
            ic.insertRow(r)
    del ic
    arcpy.AddMessage("Analysis completed - %s seggestions found!" % str(counter))
    arcpy.AddMessage(suggestions_FC)
    #arcpy.SetParameter(1, suggestions_FC)
    params = arcpy.GetParameterInfo()
    if os.path.exists(symbologyLyrx):
        params[1].symbology = symbologyLyrx
    #if output has features with length == zero : add warning
    if hasZeroLengthFeatures:
        arcpy.AddWarning("Pay attention to features that only touch in one point (length = 0)")
else:
    arcpy.AddMessage("Analysis completed - no seggestions found!")

arcpy.management.Delete(links_table)

















#
