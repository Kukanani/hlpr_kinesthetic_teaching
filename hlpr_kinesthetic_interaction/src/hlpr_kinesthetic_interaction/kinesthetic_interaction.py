#!/usr/bin/env python

# Copyright (c) 2016, Diligent Droids
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of hlpr_simulator nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Author: Vivian Chu, vchu@diligentdroids.com

"""
kinesthetic_interaction.py

This is an abstract class that controls speech interactions with the robot.
The basic low-level commands are applied in this class and extensions of
this class allow for extra functionality to be added to each speech command
as well as additional commands
"""

import roslib
import rospy
from abc import ABCMeta, abstractmethod

from std_msgs.msg import String

from hlpr_speech_recognition.speech_listener import SpeechListener
from hlpr_speech_msgs.msg import StampedString
from hlpr_speech_msgs.srv import SpeechService
from hlpr_speech_synthesis import speech_synthesizer
from hlpr_kinesthetic_interaction.srv import KinestheticInteract

class KinestheticInteraction:

    __metaclass__ = ABCMeta
    # TODO: REMOVE THIS AND PUT SOMEONE GLOBAL?
    RIGHT = 0
    LEFT = 1

    def __init__(self, verbose = True, is7DOF = False):

        # Get topic that we should be listening to for speech commands
        # self.sub_topic = rospy.get_param(SpeechListener.COMMAND_TOPIC_PARAM, None)
        # if self.sub_topic is None:
        #     rospy.logerr("Exiting: No speech topic given, is speech listener running?")
        #     exit()

        # Wait for speech listener
        # self.service_topic = rospy.get_param(SpeechListener.SERVICE_TOPIC_PARAM, None)
        # rospy.logwarn("Waiting for speech service")
        # rospy.wait_for_service(self.service_topic)
        # self.speech_service = rospy.ServiceProxy(self.service_topic, SpeechService) 
        # rospy.logwarn("Speech service loaded")

        # Initialize speech dictionary
        # self._init_speech_dictionary()

        # Initialize speech synthesis
        # self.speech = speech_synthesizer.SpeechSynthesizer()
        self.last_command = None

        # Set flag for whether we're in kinesthetic mode
        self.active = False # Default is false

        # Set flag for whether to speak responses
        self.verbose = verbose
    
        # Create a service for kinesthetic mode
        self.k_service = rospy.Service('kinesthetic_interaction', KinestheticInteract, self.toggleKMode)

        # Get access to the gravity compensation service and gripper
        # WARN: You MUST have set the arm_class variable in the class that
        # extends this
        self.arm = self.arm_class(is7DOF)

        # Initialize callback for speech commands - do at the end to prevent unwanted behavior
        # self._msg_type = eval(rospy.get_param(SpeechListener.COMMAND_TYPE, None))
        # rospy.Subscriber(self.sub_topic, self._msg_type, self._speechCB, queue_size=1) 

        # Commands used in this base class
        self.k_mode_commands = ["open_hand", "close_hand", "start_gc", "end_gc", "keyframe_start", "keyframe", "keyframe_end"]

        rospy.loginfo("Finished initializing Kinesthetic Interaction node. Service is currently set to: "+str(self.active))

    def _init_speech_dictionary(self):

        self.keywords = rospy.get_param(SpeechListener.KEYWORDS_PARAM, None)
        self.switcher = dict()
    
        # Cycle through all of the possible speech commands
        # NOTE: This assumes that there exist a function with the syntax
        # self._speech_command. Otherwise, the command is ignored
        skip_commands = []
        for command in self.keywords.keys():

            cmd_function = "_"+command.lower()
            if cmd_function in dir(self):
                self.switcher[command] = eval("self."+cmd_function)
            else:
                skip_commands.append(command)
        rospy.loginfo("No function in kinesthetic teaching for commands: %s", ', '.join(skip_commands))

    def toggleKMode(self, req):
        self.active = req.enableKInteract # pull out what the request sent
        rospy.loginfo("Kinesthetic Interaction set to: %s" % self.active)
        return True

    def _speechCB(self, msg):

        # Pull the speech command
        try:
            response = self.speech_service(True)
            self.last_command = response.speech_cmd
        except rospy.ServiceException:
            rospy.logerr("No last speech command")
            self.last_command = None

        if self.active:
            # Get the function from switcher dictionary
            func = self.switcher.get(self.last_command, self._command_not_found)         
       
            # execute the function
            func()

        else:
            if self.last_command.lower() in self.k_mode_commands:
                rospy.logwarn("Kinesthetic Mode is inactive currently")

    def _command_not_found(self):
        if self.verbose:
            rospy.logwarn("Speech command unknown: %s" % self.last_command)

    def add_speech_commands(self, speech_cmd, func):
        self.switcher[speech_cmd] = func

    # These are the commands that are set in advance and correspond to actual robot state changes
    # Extend this class and the functions in the next section 
        
    def _open_hand(self):
        self.arm.gripper.open()
        if self.verbose:
            self.speech.say("OK")
        self.apply_hand_action(self.last_command, KinestheticInteraction.RIGHT)

    def _close_hand(self):
        self.arm.gripper.close()
        if self.verbose:
            self.speech.say("OK")
        self.apply_hand_action(self.last_command, KinestheticInteraction.RIGHT)

    def _open_hand_left(self):
        self.apply_hand_action(self.last_command, KinestheticInteraction.LEFT)

    def _close_hand_left(self):
        self.apply_hand_action(self.last_command, KinestheticInteraction.LEFT)

    def _start_gc(self):
        response = self.arm.gravity_comp(True)
        if response:
            self.apply_arm_action(self.last_command, KinestheticInteraction.RIGHT)
            if self.verbose:
                self.speech.say("OK")
        else:
            rospy.logerr("Gravity compensation is not active.")

    def _end_gc(self):
        response = self.arm.gravity_comp(False)
        if response:
            self.apply_arm_action(self.last_command, KinestheticInteraction.RIGHT)
            if self.verbose:
                self.speech.say("OK")
        else:
            rospy.logerr("Gravity compensation is still active.")

    def _keyframe_start(self):
        self.demonstration_start(self.last_command)

    def _keyframe(self):
        self.demonstration_keyframe(self.last_command)

    def _keyframe_end(self):
        self.demonstration_end(self.last_command)

    def _record_all_start(self):
        self.demonstration_start_trajectory(self.last_command)

    def _record_all_end(self):
        self.demonstration_end_trajectory(self.last_command)

    ## all of the functions that need to be filled in with your own behaviors  

    @abstractmethod
    def apply_hand_action(self, cmd, hand): pass

    @abstractmethod
    def apply_arm_action(self, cmd, arm): pass

    @abstractmethod
    def demonstration_start(self, cmd): pass

    @abstractmethod
    def demonstration_keyframe(self, cmd): pass

    @abstractmethod
    def demonstration_end(self, cmd): pass

    @abstractmethod
    def demonstration_start_trajectory(self, cmd): pass
 
    @abstractmethod
    def demonstration_end_trajectory(self, cmd): pass

    
if __name__== "__main__":
    kinesthetic_interaction = KinestheticInteraction()

