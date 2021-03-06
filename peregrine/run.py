#!/usr/bin/env python

# Copyright (C) 2012 Swift Navigation Inc.
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import sys
import argparse
import cPickle
import logging
from operator import attrgetter

from peregrine.samples import load_samples
from peregrine.acquisition import Acquisition, load_acq_results, save_acq_results
from peregrine.navigation import navigation
from peregrine.tracking import track
from peregrine.log import default_logging_config
import defaults

from initSettings import initSettings

def main():
  default_logging_config()

  # Initialize constants, settings
  settings = initSettings()

  parser = argparse.ArgumentParser()
  parser.add_argument("file",
                      help="the sample data file to process")
  parser.add_argument("-a", "--skip-acquisition",
                      help="use previously saved acquisition results",
                      action="store_true")
  parser.add_argument("-t", "--skip-tracking",
                      help="use previously saved tracking results",
                      action="store_true")
  parser.add_argument("-n", "--skip-navigation",
                      help="use previously saved navigation results",
                      action="store_true")
  parser.add_argument("-f", "--file-format", default=defaults.file_format,
                      help="the format of the sample data file "
                      "(e.g. 'piksi', 'int8', '1bit')")
  args = parser.parse_args()
  settings.fileName = args.file

  samplesPerCode = int(round(settings.samplingFreq /
                             (settings.codeFreqBasis / settings.codeLength)))

  # Do acquisition
  acq_results_file = args.file + ".acq_results"
  if args.skip_acquisition:
    logging.info("Skipping acquisition, loading saved acquisition results.")
    try:
      acq_results = load_acq_results(acq_results_file)
    except IOError:
      logging.critical("Couldn't open acquisition results file '%s'.",
                       acq_results_file)
      sys.exit(1)
  else:
    # Get 11ms of acquisition samples for fine frequency estimation
    acq_samples = load_samples(args.file, 11*samplesPerCode,
                               settings.skipNumberOfBytes,
                               file_format=args.file_format)
    acq = Acquisition(acq_samples)
    acq_results = acq.acquisition()

    try:
      save_acq_results(acq_results_file, acq_results)
      logging.debug("Saving acquisition results as '%s'" % acq_results_file)
    except IOError:
      logging.error("Couldn't save acquisition results file '%s'.",
                    acq_results_file)

  # Filter out non-acquired satellites.
  acq_results = [ar for ar in acq_results if ar.status == 'A']

  if len(acq_results) == 0:
    logging.critical("No satellites acquired!")
    sys.exit(1)

  acq_results.sort(key=attrgetter('snr'), reverse=True)

  # Track the acquired satellites
  track_results_file = args.file + ".track_results"
  if args.skip_tracking:
    logging.info("Skipping tracking, loading saved tracking results.")
    try:
      with open(track_results_file, 'rb') as f:
        track_results = cPickle.load(f)
    except IOError:
      logging.critical("Couldn't open tracking results file '%s'.",
                       track_results_file)
      sys.exit(1)
  else:
    signal = load_samples(args.file,
                          int(settings.samplingFreq*1e-3*(settings.msToProcess+22)),
                          settings.skipNumberOfBytes,
                          file_format=args.file_format)
    track_results = track(signal, acq_results, settings.msToProcess)
    try:
      with open(track_results_file, 'wb') as f:
        cPickle.dump(track_results, f, protocol=cPickle.HIGHEST_PROTOCOL)
      logging.debug("Saving tracking results as '%s'" % track_results_file)
    except IOError:
      logging.error("Couldn't save tracking results file '%s'.",
                    track_results_file)

  # Do navigation
  nav_results_file = args.file + ".nav_results"
  if not args.skip_navigation:
    nav_solns = navigation(track_results, settings)
    nav_results = []
    for s, t in nav_solns:
      nav_results += [(t, s.pos_llh, s.vel_ned)]
    with open(nav_results_file, 'wb') as f:
      cPickle.dump(nav_results, f, protocol=cPickle.HIGHEST_PROTOCOL)
    logging.debug("Saving navigation results as '%s'" % nav_results_file)

if __name__ == '__main__':
  main()

