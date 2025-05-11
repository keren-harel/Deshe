# -*- coding: utf-8 -*-
import arcpy, os, math

#VARIABLES:
natua_possibilities = [
    "עשבוני",
    "בתה",
    "שיחייה",
    "חורש",
]
distanceThreshold = 113
maxTrials = 3

omdim_FC = arcpy.GetParameter(0)
processSelectedFeatures = arcpy.GetParameter(1)
if not processSelectedFeatures:
    #@validate
    omdim_FC = arcpy.Describe(omdim_FC).catalogPath
outputFC = arcpy.GetParameter(3)
output_location = arcpy.Describe(outputFC).path
output_FCName = arcpy.Describe(outputFC).basename

#natua_fieldName = 'MainForestLayerVegForm2' #PARAMETER
natua_fieldName = arcpy.GetParameter(2)

output_FieldOmedObjecID = "omedFID"
output_FieldBelowThreshold = "distanceBelowThreshold"

toBeDeleted = set()
intermediateWorkspace = "in_memory"

bigFN = os.path.join(intermediateWorkspace, "bigFN")
toBeDeleted.add(bigFN)
clipFC = os.path.join(intermediateWorkspace, "clipFC")
toBeDeleted.add(clipFC)
clippedFN = os.path.join(intermediateWorkspace, "clippedFN")
toBeDeleted.add(clippedFN)
clippedFN_k = os.path.join(intermediateWorkspace, "clippedFN_k")
toBeDeleted.add(clippedFN_k)


#FUNCTIONS:
def getN(A_dunam):
    # 04/19/24 Changing the threshold value from 60 to 40 dunams
    # 21/02/25 Changing the threshold value from 40 to 60 dunams
    if A_dunam <= 60: 
        return 1
    else:
	    return int(math.ceil(A_dunam/60.0))

def getOidFieldName(fc):
    #returns the Objectid field of a fc.
    fc_desc = arcpy.Describe(fc)
    oidFieldName = fc_desc.oidFieldName
    del fc_desc
    return oidFieldName

def addXYFields(FC):
    arcpy.management.AddField(FC, "X", "FLOAT")
    arcpy.management.AddField(FC, "Y", "FLOAT")
    uc = arcpy.UpdateCursor(FC)
    for r in uc:
        s = r.getValue('shape')
        cen = s.centroid
        r.setValue("X", cen.X)
        r.setValue("Y", cen.Y)
        uc.updateRow(r)

def fishnet(inputt, outputt):
    cellSize = 10
    extent = arcpy.Describe(inputt).extent
    #rotation = 0 ---> edit Y coordinate:
    yCo = extent.lowerLeft
    yCo.Y += 10

    arcpy.management.CreateFishnet(outputt,
                                   "%s %s" % (extent .lowerLeft.X, extent .lowerLeft.Y),
                                   "%s %s" % (yCo.X, yCo.Y),
                                   cellSize,
                                   cellSize,
                                   None,
                                   None,
                                   labels = "NO_LABELS",
                                   template = extent,
                                   geometry_type = "POLYGON")

def buildSqlQuery(fc, field, value):
    #takes:
    #   fc = feature class.
    #   field = field name... sure... (string)
    #   value = the value to which the WHERE clause will be equal to.
    fc_workspace = arcpy.Describe(fc).path
    field_delimited = arcpy.AddFieldDelimiters(fc_workspace, field)
    sql_exp = """{0} = {1}""".format(field_delimited, value)
    return sql_exp

def getBoundary(fc):
    #returns boundary of FIRST feature
    sc = arcpy.SearchCursor(fc)
    r = sc.next()
    s = r.getValue('shape')
    del sc
    return s.boundary()

def validateDistances(clustersList, threshold):
    #check all possible point pairs combinations in an omed.
    shapes = [c.getCube(0).centroid for c in clustersList]
    if len(shapes) <= 1:
        return True
    distances = []
    for i in range(len(shapes)):
        for j in range(i+1,len(shapes)):
            distances.append(shapes[i].distanceTo(shapes[j]))
    if min(distances) < threshold:
        return False
    else:
        return True

#CLASS:
class Omed:
    def __init__(self, row, oidField):
        self.id = row.getValue(oidField)
        self.polygon = row.getValue('shape')
        self.isNatua = row.getValue(natua_fieldName) not in natua_possibilities
        self.maxTrialsReached = False
        if self.polygon: #only if it's not None:
            #N = number of points to be returned for this polygon:
            if self.isNatua:
                area_dunam = self.polygon.getArea(units = "SQUAREMETERS")/1000
                self.N = getN(area_dunam)
            else:
                self.N = 1

            #clip bigFN by clipFC and get clippedFN:
            sql_clause = buildSqlQuery(omdim_FC, oidField, self.id)
            arcpy.analysis.Select(omdim_FC, clipFC, sql_clause)
            arcpy.analysis.Clip(bigFN, clipFC, clippedFN, None)
            addXYFields(clippedFN)

            trial = 0
            distancesAreValid = False
            while (not distancesAreValid) and trial < maxTrials:
                #debug:
                if trial > 0 :
                    arcpy.AddMessage("%s initiating trial no.%s" % (self.id, trial))
                self.clusters = []
                if self.N > 1:
                    arcpy.MultivariateClustering_stats(clippedFN, clippedFN_k,
                                                       ["X", "Y"], "K_MEANS",
                                                        "OPTIMIZED_SEED_LOCATIONS", None, self.N)
                    for n in range(1,self.N+1):
                        cluster = Cluster(clippedFN_k, n, self)
                        self.clusters.append(cluster)
                else:
                    #N == 1
                    cluster = Cluster(clippedFN, self.N, self)
                    self.clusters.append(cluster)

                distancesAreValid = validateDistances(self.clusters, distanceThreshold)
                trial += 1
            #if maximum of trials are reached - go on with these clusters,
            #raise a warning (during crusor↓), and mention in attributes.
            if trial == maxTrials:
                self.maxTrialsReached = True

class Cluster:
    def __init__(self, kMeansFC, clusterID, omed):
        fcBasename = "cluster_%s" % clusterID
        if omed.N > 1:
            sql_clause = buildSqlQuery(kMeansFC, "CLUSTER_ID", clusterID)
            clusterFC = os.path.join(intermediateWorkspace, fcBasename)
            toBeDeleted.add(clusterFC)
            arcpy.analysis.Select(kMeansFC, clusterFC, sql_clause)
        else:
            #it is not a k-means Feature class, but it represents
            clusterFC = kMeansFC

        dissolvedFC = os.path.join(intermediateWorkspace, fcBasename + "dissolved")
        toBeDeleted.add(dissolvedFC)
        arcpy.management.Dissolve(clusterFC, dissolvedFC, None, None, "MULTI_PART", "DISSOLVE_LINES")
        #get boundary of cluster:
        self.boundary = getBoundary(dissolvedFC)

        #create cubes and insert into cluster:
        self.cubes = []
        sc = arcpy.SearchCursor(clusterFC)
        for r in sc:
            shape = r.getValue('shape')
            cube = Cube(shape, self)
            cube.cluster = self
            self.cubes.append(cube)
        del sc

        #short cubes by distanceToBoundary, descending
        self.cubes.sort(key=lambda c: c.distanceToBoundary, reverse=True)

    def getCube(self, rank):
        #returns the cube number-<rank> highest distanceToBoundary
        #rank is zero-based
        return self.cubes[rank]

class Cube:
    def __init__(self, shape, cluster):
        self.shape = shape
        self.cluster = cluster
        #centroid as pointgeometry
        self.centroid = arcpy.PointGeometry(self.shape.centroid, self.shape.spatialReference)
        self.distanceToBoundary = self.centroid.distanceTo(self.cluster.boundary)


#PROCESS:
#@VALIDATION MUST INCLUDE SR = itm!!!
if arcpy.Describe(omdim_FC).spatialreference.factoryCode != 2039:
    arcpy.AddError("Input feature class projection must be Israel_TM_Grid (2039)")

#create point FC, add fields
arcpy.management.CreateFeatureclass(output_location, output_FCName,
                                    geometry_type= "POINT",
                                    spatial_reference = arcpy.Describe(omdim_FC).spatialReference)
arcpy.management.AddField(outputFC, output_FieldOmedObjecID, "SHORT")
arcpy.management.AddField(outputFC, output_FieldBelowThreshold, "SHORT")
#arcpy.management.AddField(outputFC, "distanceToBorder", "FLOAT") #debug field

fishnet(omdim_FC, bigFN)

oidFieldName = getOidFieldName(omdim_FC)
searchC = arcpy.SearchCursor(omdim_FC)
insertC = arcpy.InsertCursor(outputFC)
for searchR in searchC:
    omed = Omed(searchR, oidFieldName)
    if omed.maxTrialsReached:
        arcpy.AddWarning("Omed objectid %s: points distance < %sm." %
                        (omed.id, distanceThreshold))
    for cluster in omed.clusters:
        cube_0 = cluster.getCube(0)
        insertR = insertC.newRow()
        insertR.setValue("shape", cube_0.centroid)
        insertR.setValue(output_FieldOmedObjecID, omed.id)
        #insertR.setValue("distanceToBorder", cube_0.distanceToBoundary)
        if omed.maxTrialsReached:
            insertR.setValue(output_FieldBelowThreshold, 1)
        insertC.insertRow(insertR)


del searchC, insertC


for item in toBeDeleted:
    arcpy.management.Delete(item)
