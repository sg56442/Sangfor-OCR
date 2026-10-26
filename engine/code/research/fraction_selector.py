"""Image-grounded canonical representation of native numeric slash fractions.
Digits are copied, never corrected. Call only on image-ruling-validated cell coordinates.
"""
import re
from fraction_geometry import fraction_bar

def choose(native_text,crop):
 m=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*',native_text)
 if not m:return None,{'reason':'not_numeric_slash'}
 signal=fraction_bar(crop)
 if not signal['has_fraction_bar']:return None,signal
 return '\\( \\frac{'+m[1]+'}{'+m[2]+'} \\)',signal
