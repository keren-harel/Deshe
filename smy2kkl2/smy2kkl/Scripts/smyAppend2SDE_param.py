#
# Append Forest SMY to kkl SDE
#
#-------------------------------------------------------------------------------
# Name:       smyAppend2SDE_param.py
# Purpose:    Append forest smy to SDE
#             
# Author:      Michael Denisyuk
#
# Created:     04-12-2023
# Last Update: 01-05-2024 Adds calculate append date routine  
#-------------------------------------------------------------------------------
import sys
import os
from datetime import datetime as dt
import pandas as pd
import numpy as np

import arcpy
import smy_functions as fn


if __name__=='__main__':

    gdb_sde_dic ={'samples':'SMY_Samples',
            'stands':'SMY_Stands',
            'samples_InvasiveSpecies':'SMY_SamplesInvasiveSpecies',
            'samples_PlantTypeCoverDistribut':'SMY_SamplesUnderstory',
            'samples_StartRepeatDominTree':'SMY_SamplesSpecies',
            'samples_VitalForest':'SMY_SamplesVitalForest',
            'stands_InvasiveSpecies':'SMY_StandsInvasiveSpecies',
            'stands_PlantTypeCoverDistribut':'SMY_StandsUnderstory',
            'stands_StartRepeatDominTree':'SMY_StandsSpecies',
            'stands_VitalForest':'SMY_StandsVitalForest'}

    try:

        gdb = arcpy.GetParameterAsText(0)
        flagDel = arcpy.GetParameter(1)
        
        aprx = 'CURRENT'
        p = arcpy.mp.ArcGISProject(aprx)
        proj_dir = p.homeFolder
        proj_gdb = p.defaultGeodatabase

        for_no = os.path.basename(gdb)[3:7]

        if not for_no.isdigit():
            arcpy.AddMessage(f'{for_no} is not forest number.')
            sys.exit()

        # SDE 
        sde = os.path.join(p.homeFolder,'kkl-db1_giscentral_kkl1.sde')
        sdeSamples = os.path.join(sde, f'SDE.SMY_Samples')
        sdeStands = os.path.join(sde, f'SDE.SMY_Stands')                                  

        arcpy.env.preserveGlobalIds = True
        arcpy.env.overwriteOutput = True

        # Check  if Null in ParentGlobalID of smy.gdb
        samples_tab_list = ['samples_InvasiveSpecies', 'samples_PlantTypeCoverDistribut',
                'samples_StartRepeatDominTree', 'samples_VitalForest']

        null_counts = 0
        for tab_name in samples_tab_list:
            tab = os.path.join(gdb, tab_name)
            arr = arcpy.da.TableToNumPyArray(tab, ['ParentGlobalID'], null_value=-1)
            df = pd.DataFrame(data=arr)
            
            nulls = len(df[df['ParentGlobalID']=='-1'])
            if nulls > 0:
                arcpy.AddWarning(f"The {tab} has {len(df[df['ParentGlobalID']=='-1'])} null values")
            null_counts += nulls

        if null_counts > 0:
            arcpy.AddWarning('Stop tool! First need to handle NULL values in the field ParentGlobalID.')
            sys.exit()

        # Check forest number in smy data
        # Get nulls in field 'FOR_NO' of samples and stands layers in smy<for_no>.gdb

        fields = ['FOR_NO']
        layer_name = 'samples'
        for layer_name in ['samples', 'stands']:

            gdb_name = os.path.basename(gdb)
            layer = os.path.join(gdb, layer_name)
            arr = arcpy.da.TableToNumPyArray(layer, fields, null_value=-1)
            df = pd.DataFrame(data=arr).reset_index()
            grp = df[df['FOR_NO']== -1].groupby(['FOR_NO']).count()
            if len(grp.values) > 0:
                arcpy.AddWarning(f'The {layer_name} layer has {grp.values[0][0]} nulls in FOR_NO field.')
                sys.exit()

        # Delete existing records
        for l in [sdeSamples, sdeStands]:
            todel = 'xxdel'
            if not arcpy.Exists(l):
                arcpy.AddError(f'SDE layer {l} does not exist')
                sys.exit()
            arcpy.management.MakeFeatureLayer(l, todel, f'FOR_NO={for_no}')
            cnt = int(arcpy.management.GetCount(todel)[0])
            if cnt > 0:
                if flagDel:
                    arcpy.management.DeleteFeatures(todel)
                    arcpy.AddMessage(f'{cnt} features of {os.path.basename(l)} layer deleted')
                else:
                    arcpy.AddWarning(f'The data of forest {for_no} already exists.')
                    sys.exit()
        del todel
        
        for gdbObjectName in gdb_sde_dic:
            gdbObject = os.path.join(gdb, gdbObjectName)
            
            # Check GlobalID
            if not arcpy.da.Describe(gdbObject)['hasGlobalID']:
                arcpy.management.AddGlobalIDs(gdbObject)
                arcpy.AddMessage(f'GlogalID added to {gdbObject}')
            sdeObjectName = gdb_sde_dic[gdbObjectName]
            sdeObject = os.path.join(sde, f'SDE.{sdeObjectName}')

            # Append forest data to SDE
            if arcpy.Exists(sdeObject):
##                with arcpy.da.Editor(sde) as edit:
                arcpy.management.Append(gdbObject, sdeObject, 'NO_TEST')
                arcpy.AddMessage (f'{gdbObjectName} records added to {sdeObjectName}')
            else:
                arcpy.AddError(f'The SDE object {sdeObject} does not exists.')
                sys.exit()
        
        ######################################################
        #   Calculate AppendDate values in SDE layer
        ######################################################
        appenddate = dt.today().date()
        fields = ['FOR_NO', 'AppendDate']
        expr = f'FOR_NO={for_no}'
        for l in [sdeSamples, sdeStands]:
            with arcpy.da.Editor(sde) as edit:
                with arcpy.da.UpdateCursor(l, fields, expr) as uCur:
                    for row in uCur:
                        row[1] = appenddate
                        uCur.updateRow(row)
            arcpy.AddMessage (f'The date {appenddate} added AppendDate')
        
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(e)
        print(f'{exc_type} {fname} {exc_tb.tb_lineno}')
        arcpy.AddError(e)
        arcpy.AddError(f'{exc_type} {fname} {exc_tb.tb_lineno}')
