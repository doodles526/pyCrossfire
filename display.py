from SimpleCV import Camera
from SimpleCV import Color
from multiprocessing import Process, Lock
from multiprocessing.sharedctypes import Array
from ctypes import Structure, c_int
import re
import time


class Vector(Structure):
    """
    process-safe positioning
    """
    _fields_ = [('x', c_int), ('y', c_int)]


class FieldAnalyzer(Process):
    def __init__(self, cam_num, debug=False):
        Process.__init__(self)
        self.cam = Camera(cam_num, threaded=False)
        self.puck_locations = Array(Vector, [(-1, -1), (-1, -1)])
        self.puck_velocity = Array(Vector, [(-1, -1), (-1, -1)])
        self.gun_positions = Array(Vector, [(-1, -1), (-1, -1)])
        self.debug = debug
        self.field_crop_boundary = list()
        self.field_post_crop_limits = [5000, 0]   # [left, right]
        self.crop_points = list()
        self.lighting_constant = 250

    def run(self):
        now_time = time.time()
        while True:
            img = self.cam.getImage()\
                .regionSelect(self.crop_points[0],
                              self.crop_points[1],
                              self.crop_points[2],
                              self.crop_points[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=self.lighting_constant).invert()
            blobs = img.findBlobsFromMask(mask)

            if blobs:
                for i in range(2):
                    if len(blobs) > i:
                        self.puck_locations[i].x = blobs[i].coordinates()[0]
                        self.puck_locations[i].y = blobs[i].coordinates()[1]

            if self.debug:
                old_time = now_time
                now_time = time.time()
                fps = 1/(now_time - old_time)
                if blobs:
                    blobs.draw(width=4)
                    print "FPS: " + str(fps) + "Puck Locations: " + \
                        str(self.puckLocations()) + \
                        " Percent progression: " + \
                        str(self.puckLocationsPercent())
                img.show()

    def puckLocations(self):
        """
        API proxy for accessing puck locations so user doesn't have to
        deal with weird c_type memory
        """
        return [(self.puck_locations[0].x, self.puck_locations[0].y),
                (self.puck_locations[1].x, self.puck_locations[1].y)]

    def puckLocationsPercent(self):
        """
        Returns the percent the puck has progressed over the field
        0% is left most, 100% is right most
        """
        motorA = ((self.field_post_crop_limits[1] -
                   self.field_post_crop_limits[0]) -
                  (self.field_post_crop_limits[1] -
                   self.puck_locations[0].x)) / \
            float(self.field_post_crop_limits[1] -
                  self.field_post_crop_limits[0])

        motorB = ((self.field_post_crop_limits[1] -
                   self.field_post_crop_limits[0]) -
                  (self.field_post_crop_limits[1] -
                   self.puck_locations[1].x)) / \
            float(self.field_post_crop_limits[1] -
                  self.field_post_crop_limits[0])

        if motorA > 1:
            motorA = 1
        elif motorA < 0:
            motorA = 0

        if motorB > 1:
            motorB = 1
        elif motorB < 0:
            motorB = 0

        return (motorA, motorB)

    def calibrate(self):
        """
        A calibration tool which gives gui for calibrating
        """

        #####################INITIAL FIELD POINT CALIBRATION###################
        print "We are displaying a live feed from the cam.  Click " \
              "on a point of the field we tell you, then enter that info\n\n"
        print "Click top-left of field, then right click\n"

        self.cam.live()
        top_left = raw_input("Enter the coord value: ")

        print "\nClick top-right, then right click\n"
        self.cam.live()
        top_right = raw_input("Enter the coord value: ")

        print "\nClick the bottom left, then click right\n"
        self.cam.live()
        bottom_left = raw_input("Enter the coord value: ")

        print "\nClick bottom right, then right click\n"
        self.cam.live()
        bottom_right = raw_input("Enter the coord value: ")

        top_left = tuple(int(v) for v in re.findall("[0-9]+", top_left))
        top_right = tuple(int(v) for v in re.findall("[0-9]+", top_right))
        bottom_left = tuple(int(v) for v in re.findall("[0-9]+", bottom_left))
        bottom_right = tuple(int(v) for v in re.findall("[0-9]+",
                             bottom_right))

        locations = [5000, 0, 5000, 0]  # left, top, right, bottom

        if top_left[0] < bottom_left[0]:
            locations[0] = top_left[0]
        else:
            locations[0] = bottom_left[0]
        if top_right[0] > bottom_right[0]:
            locations[2] = top_right[0]
        else:
            locations[2] = bottom_right[0]
        if top_left[1] < top_right[1]:
            locations[1] = top_left[1]
        else:
            locations[1] = top_right[1]

        if bottom_right[1] < bottom_left[1]:
            locations[3] = bottom_left[1]
        else:
            locations[3] = bottom_right[1]
        self.field_crop_boundary.append((bottom_left[0] - locations[0],
                                         top_left[1] - locations[1]))
        self.field_crop_boundary.append((bottom_right[0] - locations[0],
                                         top_right[1] - locations[1]))
        self.field_crop_boundary.append((top_right[0] - locations[0],
                                         bottom_right[1] - locations[1]))
        self.field_crop_boundary.append((top_left[0] - locations[0],
                                         bottom_left[1] - locations[1]))

        self.crop_points = locations
        #######################################################################
        #######################################################################

        #############################Lighting Calibration######################
        inVal = 200

        print "We are now starting calibration for lighting."
        while inVal != -1:

            img = self.cam.getImage() \
                .regionSelect(locations[0],
                              locations[1],
                              locations[2],
                              locations[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=inVal).invert()
            blobs = img.findBlobsFromMask(mask)
            if blobs:
                blobs.draw()
            img.show()
            self.lighting_constant = inVal
            inVal = int(raw_input("Enter new thresh val for blobs, "
                                  "then -1 to confirm lighting calibration: "))
            print "\n"
        #######################################################################
        #######################################################################

        ##################Post Crop Field Determination########################
        temp_positions = [0, 0, 0, 0]
        inVal = ""
        print "We are now taking some simple measurements " \
              "of the post-cropped playing field."

        ####################Upper Left Determination###########################
        raw_input("Place the puck in the upper-left most "
                  "side of the field and press [Enter]")
        while not re.match(r"[yY]", inVal):

            img = self.cam.getImage()   \
                .regionSelect(locations[0],
                              locations[1],
                              locations[2],
                              locations[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=self.lighting_constant).invert()
            blobs = img.findBlobsFromMask(mask)
            if blobs:
                blobs[0].draw()
                print blobs[0]
                temp_positions[0] = blobs[0].coordinates()[0]
            img.show()
            inVal = str(raw_input("Enter y/Y if the puck is selected, and the "
                                  "displayed coordinate appears reasonable, "
                                  "otherwise just hit [Enter]"))
        #######################################################################

        #######################Upper Right Determinstaion######################
        inVal = ""
        raw_input("Place the puck in the upper-right most side "
                  "of the field and press [Enter]")
        while not re.match(r"[yY]", inVal):

            img = self.cam.getImage() \
                .regionSelect(locations[0],
                              locations[1],
                              locations[2],
                              locations[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=self.lighting_constant).invert()
            blobs = img.findBlobsFromMask(mask)
            if blobs:
                blobs[0].draw()
                print blobs[0]
                temp_positions[2] = blobs[0].coordinates()[0]
            img.show()
            inVal = raw_input("Enter y/Y if the puck is selected, and the "
                              "displayed coordinate appears reasonable, "
                              "otherwise just hit [Enter]")
        #######################################################################

        ######################Bottom Left Determination########################
        inVal = ""
        raw_input("Place the puck in the bottom-left most "
                  "side of the field and press [Enter]")
        while not re.match(r"[yY]", inVal):

            img = self.cam.getImage() \
                .regionSelect(locations[0],
                              locations[1],
                              locations[2],
                              locations[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=self.lighting_constant).invert()
            blobs = img.findBlobsFromMask(mask)
            if blobs:
                blobs[0].draw()
                print blobs[0]
                temp_positions[1] = blobs[0].coordinates()[0]
            img.show()
            inVal = raw_input("Enter y/Y if the puck is selected, and the "
                              "displayed coordinate appears reasonable, "
                              "otherwise just hit [Enter]")
        #######################################################################

        ####################Bottom Right Determination#########################
        inVal = ""
        raw_input("Place the puck in the bottom-right most "
                  "side of the field and press [Enter]")
        while not re.match(r"[yY]", inVal):

            img = self.cam.getImage() \
                .regionSelect(locations[0],
                              locations[1],
                              locations[2],
                              locations[3]) \
                .warp(self.field_crop_boundary)
            mask = img.binarize(thresh=self.lighting_constant).invert()
            blobs = img.findBlobsFromMask(mask)
            if blobs:
                blobs[0].draw()
                print blobs[0]
                temp_positions[3] = blobs[0].coordinates()[0]
            img.show()
            inVal = raw_input("Enter y/Y if the puck is selected, and the "
                              "displayed coordinate appears reasonable, "
                              "otherwise just hit [Enter]")
        #######################################################################

        ###################Assigning Limits for post-Crop######################
        if temp_positions[0] < temp_positions[1]:
            self.field_post_crop_limits[0] = temp_positions[0]
        else:
            self.field_post_crop_limits[0] = temp_positions[1]

        if temp_positions[2] > temp_positions[3]:
            self.field_post_crop_limits[1] = temp_positions[2]
        else:
            self.field_post_crop_limits[1] = temp_positions[3]
        #######################################################################

        #######################################################################
        #######################################################################

        print self.crop_points
        print self.field_crop_boundary
