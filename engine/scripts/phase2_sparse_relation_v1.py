"""Paired horizontal strokes among source glyph bands; no text recognition."""
import cv2
import numpy as np


def relation_features(image, census_features):
    thumb = image.copy()
    thumb.thumbnail((1200,1200))
    gray = np.asarray(thumb.convert('L'))
    _, _, stats, _ = cv2.connectedComponentsWithStats((gray < 180).astype('uint8'),8)
    strokes = [(i,list(map(int,s))) for i,s in enumerate(stats[1:],1)
               if s[4] >= 8 and s[2] >= 2.5*s[3]]
    pairs = []
    for band_index, band in enumerate(census_features['bands']):
        box, glyph_height = band['box'], band['median_height']
        center = (box[1]+box[3])/2
        candidates = [(i,s) for i,s in strokes
                      if .5*glyph_height <= s[2] <= 2.5*glyph_height
                      and s[3] <= .3*glyph_height
                      and box[0] <= s[0] and s[0]+s[2] <= box[2]
                      and abs(s[1]+s[3]/2-center) <= .6*glyph_height]
        for index,(i,a) in enumerate(candidates):
            for j,b in candidates[index+1:]:
                upper,lower = sorted([a,b],key=lambda s:s[1])
                gap = lower[1]-(upper[1]+upper[3])
                overlap = max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))
                if (overlap >= .8*max(a[2],b[2]) and min(a[2],b[2]) >= .75*max(a[2],b[2])
                    and .5 <= a[3]/b[3] <= 2 and min(a[3],b[3]) <= gap <= .6*glyph_height):
                    pairs.append(dict(band_index=band_index, component_ids=[i,j], strokes=[a,b]))
    return dict(eligible=bool(pairs), pairs=pairs,
                interpretation='Paired horizontal-stroke risk, not proof of an equals sign or correct formula.')
