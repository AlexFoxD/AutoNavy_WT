"""Legacy pure template helpers; capture is owned by autonavy.capture.factory."""
import cv2

RECT = (0, 0, 0, 0)


def match_img(bg, tp, m):
    global RECT
    """Find a template in a background image and return its center and score.

    ``bg`` is the background image and ``tp`` is the template image.
    """
    # Prepare the background and template images.

    # pic_name = tp.split('/')[-1].split('.')[0]
    # bg_img = cv2.imread(bg)  # Background image.
    tp_img = tp  # Template image.

    # Extract image edges.
    bg_edge = cv2.Canny(bg, 100, 200)
    tp_edge = cv2.Canny(tp_img, 100, 200)
    bg_pic = cv2.cvtColor(bg_edge, cv2.COLOR_BGR2BGRA)
    tp_pic = cv2.cvtColor(tp_edge, cv2.COLOR_BGR2BGRA)

    # Match the template.
    res = cv2.matchTemplate(bg_pic, tp_pic, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  # Find the best match.
    # print('Maximum match score:', max_val)
    if max_val < m:
        return -1, max_val
    # Calculate the matching rectangle.
    th, tw = tp_pic.shape[:2]
    tl = max_loc  # Top-left corner.
    br = (tl[0] + tw, tl[1] + th)  # Bottom-right corner.
    center = (tl[0] + br[0]) // 2 + RECT[0], (tl[1] + br[1]) // 2 + RECT[1]
    # return (tl, br), max_val
    return center, max_val


def match_img_ltrb(bg, tp, m):
    global RECT
    """Find a template and return its bounding rectangle and score.

    ``bg`` is the background image and ``tp`` is the template image.
    """
    # Prepare the background and template images.

    # pic_name = tp.split('/')[-1].split('.')[0]
    # bg_img = cv2.imread(bg)  # Background image.
    tp_img = tp  # Template image.

    # Extract image edges.
    bg_edge = cv2.Canny(bg, 100, 200)
    tp_edge = cv2.Canny(tp_img, 100, 200)
    bg_pic = cv2.cvtColor(bg_edge, cv2.COLOR_BGR2BGRA)
    tp_pic = cv2.cvtColor(tp_edge, cv2.COLOR_BGR2BGRA)

    # Match the template.
    res = cv2.matchTemplate(bg_pic, tp_pic, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  # Find the best match.
    # print('Maximum match score:', max_val)
    if max_val < m:
        return -1, max_val
    # Calculate the matching rectangle.
    th, tw = tp_pic.shape[:2]
    tl = max_loc  # Top-left corner.
    br = (tl[0] + tw, tl[1] + th)  # Bottom-right corner.
    # center = (tl[0] + br[0]) // 2 + RECT[0], (tl[1] + br[1]) // 2 + RECT[1]
    return (tl, br), max_val
    # return center, max_val
