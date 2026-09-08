import ctypes
import time

import cv2
import numpy as np
import dxcam
import win32gui
from toolkit.th_pool import thread_control


user32 = ctypes.windll.user32
screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


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


class dxgi_screen_shot:
    def __init__(self):
        self.FPS = 1000
        self.region = (0, 0, screensize[0], screensize[1])

    def init(self):
        self.camera = dxcam.create(device_idx=0, output_color="BGRA")
        self.update_region()
        # self.camera.start(region=self.region, target_fps=self.FPS)

    def update_region(self):
        global RECT
        try:
            rect = win32gui.GetWindowRect(win32gui.FindWindow('DagorWClass', None))
            left = rect[0] + 3
            top = rect[1] + 32
            right = rect[2] - 3
            bottom = rect[3] - 3
            # print(left, top, right, bottom)
            self.region = (left, top, right, bottom)
            RECT = self.region
        except:
            print("Окно War Thunder не найдено; используется захват всего экрана.")
            self.region = (0, 0, screensize[0], screensize[1])

    def redirct(self):
        self.cam_status(False)
        self.update_region()
        self.cam_status(True)

    def cam_status(self, status: bool):
        if status:
            self.camera.start(region=self.region, target_fps=self.FPS, video_mode=True)
        else:
            self.camera.stop()

    def get_latest_frame(self):
        self.now_img = self.camera.get_latest_frame()
        return self.now_img

    def grab_screen_dxcam(self):
        # camera = dxcam.create(device_idx=0, output_color="BGRA")  # returns a DXCamera instance on primary monitor
        # camera.start(region=(0, 0, 2560, 1440), target_fps=1000, video_mode=True)  # Optional argument to capture a region
        # camera.is_capturing  # True
        # ... Do Something
        start = int(round(time.time() * 1000))

        for i in range(3000):
            img = self.camera.get_latest_frame()
            # cv2.imshow("image", img)
            # cv2.waitKey(1)
        print("Время захвата:", int(round(time.time() * 1000)) - start, "мс")

    def grab(self, state):
        if state:
            self.camera.start(region=self.region, target_fps=self.FPS, video_mode=True)
            self.grab_scn = thread_control.submit(self.get_latest_frame, 'grab_scn', True)
        else:
            self.camera.stop()
            self.grab_scn.stop()

    def check_grab_state(self):
        try:
            result = self.grab_scn.alive()
            return result
        except:
            return False


D = dxgi_screen_shot()
D.init()
D.grab(True)
