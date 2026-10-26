"""Single-line equation leaves separated from image connectors and other owners."""
import math
import cv2
import numpy as np


def gate(image, parent_rect, leaf, blocks, parent_index):
    if leaf.type != 'equation' or leaf.angle not in [None, 0]:
        return None, dict(reason='not_upright_equation')
    parent = image.crop(parent_rect)
    width, height = parent.size
    box = [math.floor(leaf.bbox[0]*width), math.floor(leaf.bbox[1]*height),
           math.ceil(leaf.bbox[2]*width), math.ceil(leaf.bbox[3]*height)]
    if box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height:
        return None, dict(reason='outside_parent')
    if box[2]-box[0] < .35*width or box[3]-box[1] <= 0:
        return None, dict(reason='not_wide_complete_band')
    gray = np.asarray(parent.convert('L'))
    _, _, stats, _ = cv2.connectedComponentsWithStats((gray < 180).astype('uint8'), 8)
    inside, crossing, connectors = [], [], []
    for raw in stats[1:]:
        x, y, w, h, area = map(int, raw)
        if area < 8:
            continue
        ix = max(0, min(box[2], x+w)-max(box[0], x))
        iy = max(0, min(box[3], y+h)-max(box[1], y))
        if not ix or not iy:
            continue
        component = [x,y,w,h,area]
        if (w >= .5*width or h >= .35*height) and area/(w*h) < .3:
            connectors.append(component)
        if x >= box[0] and y >= box[1] and x+w <= box[2] and y+h <= box[3]:
            inside.append(component)
        else:
            crossing.append(component)
    evidence = dict(local_box=box, inside=inside, crossing=crossing, connectors=connectors)
    if connectors:
        return None, dict(evidence, reason='connector_or_frame_intersects_equation')
    if crossing:
        return None, dict(evidence, reason='source_component_cut_at_leaf_boundary')
    if len(inside) < 4:
        return None, dict(evidence, reason='too_few_complete_components')
    typical = float(np.median([c[3] for c in inside]))
    centers = [c[1]+c[3]/2 for c in inside]
    if max(centers)-min(centers) > typical:
        return None, dict(evidence, reason='not_single_baseline')
    absolute = [box[0]+parent_rect[0], box[1]+parent_rect[1],
                box[2]+parent_rect[0], box[3]+parent_rect[1]]
    for index, block in enumerate(blocks):
        if index == parent_index or not block.get('content'):
            continue
        other = [v*(image.width if i%2 == 0 else image.height) for i,v in enumerate(block['bbox'])]
        overlap = max(0,min(absolute[2],other[2])-max(absolute[0],other[0]))*max(0,min(absolute[3],other[3])-max(absolute[1],other[1]))
        if overlap > 0:
            return None, dict(evidence, reason='existing_content_owner_intersects')
    return absolute, dict(evidence, reason='complete_single_baseline_separated_from_connectors')
