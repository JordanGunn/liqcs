# Correct dictionary of field names (key) and field types (value) for a given shapefile baseed on current specification

control_fields = {
'point_id':'String',
'obs_date':'String',
'contract':'String',
'gc_type':'String',
'descrip':'String',
'checkpoint':'String',
'processing':'String',
'h_v_datum':'String',
'geoid':'String',
'projection':'String',
'coord_e':'Real',
'coord_n':'Real',
'coord_ht':'Real',
'stdev_e':'Real',
'stdev_n':'Real',
'stdev_ht':'Real'}

swath_fields = {
'LIDAR_SYS':'String',
'SYS_SN':'String',
'ACQ_DATE':'String',
'AGL':'Real',
'PRF':'Integer'
}

final_coverage_fields = {
'acq_year':'Integer',
'contract':'String',
'prj_name':'String',
'status':'String',
'site_name':'String',
'area_sqkm':'Real',
'density':'Integer'
}

photo_centre_fields = {
'segment_id':'String',
'roll_num':'String',
'frame_num':'Real',
'image_file':'String',
'date':'String',
'time':'Real',
'flying_hei':'Real',
'latitude':'Real',
'longitude':'Real',
'dec_lat':'Real',
'dec_long':'Real',
'nts_mapshe':'String',
'bcgs_mapsh':'String',
'heading':'Real',
'solar_angl':'Real',
'sun_azimut':'Real',
'operation_':'String',
'focal_leng':'Real',
'lens_numbe':'Real',
'nominal_sc':'String',
'gsd':'Real',
'emulsion_i':'String',
'contractor':'String',
'req_agency':'String',
'aircraft':'String',
'weather':'String',
'remarks':'String',
'stereo_mod':'String',
'im_frame':'String',
'eop_type':'String',
'eop_x':'Real',
'eop_y':'Real',
'eop_z':'Real',
'omega':'Real',
'phi':'Real',
'kappa':'Real',
'eop_x_stdv':'Real',
'eop_y_stdv':'Real',
'eop_z_stdv':'Real',
'utm_zone':'Real',
'agl':'Real',
'cam_s_no':'String',
'calib_date':'String',
'patb_file':'String',
'a1':'Real',
'a2':'Real',
'a3':'Real',
'b1':'Real',
'b2':'Real',
'b3':'Real',
'c1':'Real',
'c2':'Real',
'c3':'Real'
}

tree_height_fields = {
    'Top_Elev':'Real',
    'Bot_Elev':'Real',
    'Tree_Heigh':'Real'
}