# -*- Python -*-

cdef extern from "plugininit.h":
    void c_seamless_element_init "seamless_element_init" ()

def seamless_element_init():
    c_seamless_element_init()

