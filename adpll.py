#!/usr/bin/env python3
# ADPLL for floppy disk data separator
# Copyright 2016 Eric Smith <spacewar@gmail.com>

#    This program is free software: you can redistribute it and/or
#    modify it under the terms of version 3 of the GNU General Public
#    License as published by the Free Software Foundation.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see
#    <http://www.gnu.org/licenses/>.

import argparse
import re


class ADPLL():
    def __init__(self,
                 di,
                 osc_period,
                 max_adj_pct,
                 window_pct,
                 freq_adj_factor,
                 phase_adj_factor,
                 debug = False):
        self.di = di
        self.osc_period = osc_period
        self.window_frac = window_pct / 100
        self.freq_adj_factor = freq_adj_factor
        self.phase_adj_factor = phase_adj_factor

        self.debug = debug
        self.debug_all = False

        self.min_osc_period = self.osc_period * (100 - max_adj_pct) / 100
        self.max_osc_period = self.osc_period * (100 + max_adj_pct) / 100

        self.zero_bits = 0

        # start oscillator locked to first transition
        self.trans_time = di.__next__()
        self.osc_time = self.trans_time
        #print("first transition at %g" % self.trans_time)

    def __iter__(self):
        return self

    def __next__(self):
        if self.zero_bits != 0:
            self.zero_bits -= 1
            return 0

        # We're going to return a one. Now deal with the next transition
        hbi = 0

        while hbi <= 0:
            self.trans_time += self.di.__next__()
            q = (self.trans_time - self.osc_time) / self.osc_period
            hbi = int(q + 0.5)
            self.osc_time += hbi * self.osc_period
            error = (self.trans_time - self.osc_time)

            # if (hbi <= 0):
            #     # Hopefully this only happens outside ID & data fields,
            #     # e.g., in write splices
            #     print("transition too soon")
            #     print("%g, %d, %g" % (q, hbi, error))

        #print("%g, %d, %g" % (q, hbi, error))
        if self.debug_all or (self.debug and (abs(error) > (self.osc_period * self.window_frac))):
            print("transition outside window")
            print("transition at time %g us" % (self.trans_time * 1.0e6))
            print("oscillator at time %g us" % (self.osc_time * 1.0e6))
            print("q = %f" % q)
            print("hbi = %f" % hbi)
            print("new osc time %g us" % (self.osc_time * 1.0e6))
            print("error %g" % error)
            print("osc period %g us " % (self.osc_period * 1.0e6))
            print("error limit %g us" % (self.osc_period * self.window_frac * 1.0e6))
        if True:  # was else for previous if statement
            if self.freq_adj_factor != 0:
                adj = error * self.freq_adj_factor
                self.osc_period += adj
                if self.osc_period < self.min_osc_period:
                    self.osc_period = self.min_osc_period
                    #print("osc period clipped to min")
                elif self.osc_period > self.max_osc_period:
                    self.osc_period = self.max_osc_period
                    #print("osc period clipped to max")
                #print("osc period adjusted by %g to %g" % (adj, self.osc_period))
            if self.phase_adj_factor != 0:
                adj = error * self.phase_adj_factor
                self.osc_time += adj

        self.zero_bits = hbi - 1
        #print("hbi=%d, %d zeros" % (hbi, self.zero_bits))
        
        return 1


