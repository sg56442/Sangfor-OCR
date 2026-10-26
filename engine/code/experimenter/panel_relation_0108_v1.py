"""Selector support restriction: transcription-only panel dominates one native image owner."""
def relation_gate(r,raw,image_size):
 if r['normal']:return True,'existing_text_normal_observation_only'
 if r['owner'] is None:return False,'no_unique_image_owner'
 w,h=image_size;q=raw['blocks'][r['owner']]['bbox'];x0,y0,x1,y1=r['rect'];area=(x1-x0)*(y1-y0);ownerarea=(q[2]-q[0])*w*(q[3]-q[1])*h
 if area/ownerarea<.55:return False,'panel_not_dominant_in_relation_owner'
 return True,'dominant_closed_panel_preserve_image_and_child_coordinates'
