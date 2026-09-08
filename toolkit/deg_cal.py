import ctypes
import math
import time

import cv2
import numpy as np
import dxcam
import win32gui
from toolkit import scn



D = scn.D


def get_deg():
    try:
        # Capture the current frame.
        image = D.get_latest_frame()
        image = image[545:615, 85:145]
        # cv2.imshow('Result', image)
        # cv2.waitKey(1)
        # continue

        # Convert the image to HSV color space.
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Define the target color range.
        lower_color = np.array([35, 43, 46])
        upper_color = np.array([77, 255, 255])

        center = (image.shape[1] // 2, image.shape[0] // 2)
        # print("center:", center)

        """
        Alternative range for the turret indicator's light-green color.
        lower_color = np.array([60, 100, 50])
        upper_color = np.array([80, 255, 255])
        """

        # Create the color mask.
        mask = cv2.inRange(hsv, lower_color, upper_color)

        # Apply morphological operations.
        kernel = np.ones((1, 1), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Extract aiming-line contours.
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Draw the aiming-line contours.
        for contour in contours:
            cv2.drawContours(image, [contour], -1, (0, 0, 255), 1)

        # Find the largest contour.
        max_contour = max(contours, key=cv2.contourArea)
        num = 1
        for i in range(1, 10):
            approx = cv2.approxPolyDP(max_contour, cv2.arcLength(max_contour, True) * (num - i / 10), True)
            # print("Approximated vertex count:", len(approx))
            # Calculate the angle relative to the Y axis.
            point_list = []
            if len(approx) == 3:
                # Find the vertex nearest to the center.
                min_distance = 999999
                for v in approx:
                    point_list.append((v[0][0], v[0][1]))
                    distance = np.sqrt((v[0][0] - center[0]) ** 2 + (v[0][1] - center[1]) ** 2)
                    if distance < min_distance:
                        min_distance = distance
                        vc = (v[0][0], v[0][1])
                point_list.remove(vc)

                # TODO: Measure and compensate for the offset.
                vc = (center[0], vc[1])

                v1 = point_list[0]
                v2 = point_list[1]
                # Calculate the midpoint of the other two vertices.
                ct = ((v1[0] + v2[0]) // 2, (v1[1] + v2[1]) // 2)



                ax_y = [center[0], 0]
                # Calculate the angle between segments ax_y–vc and ct–vc.
                vect_y = [ax_y[0] - vc[0], ax_y[1] - vc[1]]
                vect_ct = [ct[0] - vc[0], ct[1] - vc[1]]
                # Calculate the angle between the vectors.
                # angle_radians = np.arccos(np.dot(vect_y, vect_ct) / (np.linalg.norm(vect_y) * np.linalg.norm(vect_ct)))
                # angle_degrees = np.degrees(angle_radians)
                # return angle_degrees
                angle_radians = math.atan2(vect_ct[1], vect_ct[0])
                angle_degrees = math.degrees(angle_radians) + 90
                if angle_degrees < 0:
                    angle_degrees += 360
                if angle_degrees > 360:
                    angle_degrees -= 360
                if angle_degrees > 180:
                    angle_degrees -= 360
                return angle_degrees
                # print(f"Angle: {angle_degrees:.2f}")
                # cv2.line(image, vc, ct, (255, 255, 0), 2)
                # cv2.imshow('Result', image)
                # cv2.waitKey(1)
                # cv2.destroyAllWindows()
        for i in range(1, 10):
            approx = cv2.approxPolyDP(max_contour, cv2.arcLength(max_contour, True) * (num - i / 10), True)
            # print("Approximated vertex count:", len(approx))
            # Calculate the angle relative to the Y axis.
            point_list = []
            if len(approx) == 2:
                min_distance = 999999
                for v in approx:
                    point_list.append((v[0][0], v[0][1]))
                    distance = np.sqrt((v[0][0] - center[0]) ** 2 + (v[0][1] - center[1]) ** 2)
                    if distance < min_distance:
                        min_distance = distance
                        vc = (v[0][0], v[0][1])
                point_list.remove(vc)
                v1 = point_list[0]
                ct = ((v1[0] + vc[0]) // 2, (v1[1] + vc[1]) // 2)
                ic = (center[0], center[1]+10)

                # cv2.line(image, ic, ct, (0, 255, 255), 2)

                ax_y = [center[0], 0]
                # Calculate the angle between segments ax_y–vc and ct–vc.
                vect_y = [ax_y[0] - vc[0], ax_y[1] - vc[1]]
                vect_ct = [ct[0] - ic[0], ct[1] - ic[1]]
                # Calculate the angle between the vectors.
                angle_radians = math.atan2(vect_ct[1], vect_ct[0])
                angle_degrees = math.degrees(angle_radians) + 90
                if angle_degrees < 0:
                    angle_degrees += 360
                if angle_degrees > 360:
                    angle_degrees -= 360
                if angle_degrees > 180:
                    angle_degrees -= 360
                return angle_degrees
                # print(f"Angle: {angle_degrees:.2f}")
                # cv2.imshow('Result', image)
                # cv2.waitKey(1)
    except ValueError:
        return None


if __name__ == '__main__':
    while True:
        t1 = time.time()
        a = get_deg()
        t2 = time.time()
        print(a)
        print(t2 - t1)
