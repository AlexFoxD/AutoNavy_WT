"""Pure legacy return-shape adapters. Callers provide pixels; no capture exists here."""
import cv2

from autonavy.vision.detectors import match_edges
from autonavy.vision.templates import TemplateError, TemplateRegistry, validate_image


def match_img_ltrb(bg, tp, m):
    """Return ((left, top), (right, bottom)), score, or (-1, score)."""
    try:
        validate_image('background', bg)
        registry = TemplateRegistry()
        registry.register('legacy', tp)
        edge = registry.edges('legacy')
        score, location, reason = match_edges(cv2.Canny(bg,100,200),edge,m)
    except TemplateError:
        return -1, 0.0
    if reason or location is None:
        return -1, score if score is not None else 0.0
    return (location, (location[0]+edge.shape[1],location[1]+edge.shape[0])), score


def match_img(bg, tp, m):
    """Return a frame-relative center; desktop mapping requires a packet geometry."""
    box, score = match_img_ltrb(bg,tp,m)
    if box == -1:
        return -1, score
    return ((box[0][0]+box[1][0])//2,(box[0][1]+box[1][1])//2), score
