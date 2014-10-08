#!/usr/bin/env python
"""
Translates the Rock Corpus Dataset chord and melody annotations to a set of JAMS files.

The original data is found online at the following URL:
    http://theory.esm.rochester.edu/rock_corpus/

To parse the entire dataset, you simply need to provide the path to the
unarchived folders.

Example:


NOTES:

There are a number of issues discovered when attempting to convert this dataset to JAMS format:

1. The harmony files are assumed to have been expanded using the expand6 utility provided by the original annotators. 
Similarly, the melody files are assumed to have been expanded using the process-mel5 utility. 

2. The units of time used in both the harmony and melody annotations are measures 
(so, for example, "1.5" indicates a time half way through the second measure). 
Note that timing data can be added (e.g., using the add-timings utility), but only measure times are provided by the annotators, so 
times are approximate for events occurring at times other than beginnings of measures. Note that running add-timings will modify the harmony annotation file, 
and change the meaning of the first and second columns. Before add-timings is run, the first and second columns are the start and end times of the chord (in measures);
after add-timings is run, the first and second columns are start time in seconds and start time in measures.

3. Melodic events are represented by the MIDI note number (where middle C = 60). Because the original dataset does not inlcude duration information, 
we assume that the end time of a given note is equal to the start time of the following note. 
Harmonic events are represented by Roman Numeral, with the secondary value being the pitch class of the current key. The original
annotations provide more information, i.e. chromatic root, diatonic root, and absolute root (c.f. http://theory.esm.rochester.edu/rock_corpus/programs.html#P1).
This information can be derived from the Roman Numeral and key.

4. The expanded harmony files have an irregular format. The last line is always 3 columns; all other lines are 7 columns (regardless of whether or not add-timings has been run).

5. Only one curator is currently allowed, but this dataset seems to have two (David Temperley and Trevor de Clercq).

6. We assume that the Rock Corpus directory contains the sub-directories rs200_harmony_clt (containing the expanded harmony annotations) and rs200_melody_nlt (containing the expanded melody annotations).
This directory should also contain the file "audio_sources.txt" at the top level.


"""

__author__ = "J. P. Forsyth"
__copyright__ = "Copyright 2014, Music and Audio Research Lab (MARL)"
__license__ = "GPL"
__version__ = "1.0"
__email__ = "jpf211@nyu.edu"

import argparse
import json
import logging
import os
import sys
import tempfile
import time

sys.path.append("..")
import pyjams


AUDIO_SOURCES_FILE = 'audio_sources.txt'
ANNOTATORS = { 'dt' : 'David Temperley', 'tdc' : 'Trevor de Clercq' }


def fill_annotation_metadata(annot):
    """Fills the annotation metadata."""
    annot.annotation_metadata.corpus = "Rock Corpus"
    annot.annotation_metadata.version = "2.1"
    annot.annotation_metadata.annotation_rules = ""
    annot.annotation_metadata.data_source = "manually annotated by David Temperley and Trevor de Clercq"
    annot.annotation_metadata.curator = pyjams.Curator(name="David Temperley",
                                                       email="dtemperley@esm.rochester.edu")
    # annot.annotation_metadata.annotator = {}


def read_harmony_lab(filename,timing_added):
    """ read a .clt harmony file. all lines will have 7 columns with the exception of the last
    one, which has 3, so we have to parse everything but the last line and the last line
    separately. """

    text = pyjams.util.load_textlist(filename=filename)

    # write a temp file with all lines except last one 
    fid, fpath = tempfile.mkstemp(suffix='.txt')
    fhandle = os.fdopen(fid, 'w')
    for i in range(len(text)-1):
        fhandle.writelines(text[i]+'\n')
    fhandle.close()

    # now parse it correctly
    if timing_added:
        _, start_times, chord_labels, _ , _ , keys, _  = pyjams.util.read_lab(fpath, 7)

    else:
        start_times, end_times, chord_labels, _ , _ , keys, _ = pyjams.util.read_lab(fpath, 7)    

    # and delete temp file
    os.remove(fpath)

    # if timing information has been added, need to get end times
    if timing_added:
        end_times = start_times[1:]
        final_t = float(text[-1].split('\t')[1])
        end_times.append(final_t)

    return start_times, end_times, chord_labels, keys


def get_audio_sources_info(audio_sources_file):
    """ get information regarding audio source files. 
    Returns a dictionary that maps song names to artist and album """

    data = util.read_lab(audio_sources_file, 3, delimiter='\t')

    # make a dictionary so we can look up by song name
    songs = {}
    N = len(data[0])
    for n in range(N):
        name = data[0][n]
        songs[name] = { 'artist' : data[1][n], 'album' : data[2][n] }

    return songs


def parse_harmony_clt_file(harmony_file, jam, annotator, timing_added):
    """ given a harmony .clt file, add annotations to jam """

    start_times, end_times, chord_labels, keys = read_harmony_lab(filename=harmony_file,timing_added=timing_added)

    chord_annot = jam.chord.create_annotation()
    chord_annot.annotation_metadata.annotator = annotator

    jam.file_metadata.duration = end_times[-1]

    print '*** NEED TO ADD KEY INFORMATION ***'

    pyjams.util.fill_range_annotation_data(start_times=start_times,end_times=end_times, labels=chord_labels,range_annotation=chord_annot)
    fill_annotation_metadata(chord_annot)


def parse_melody_nlt_file(melody_file, jam, annotator, timing_added):
    """ parse a melody .nlt file, and add annotations to jam """

    if timing_added:
        _ , times, note_events, _  = pyjams.util.read_lab(melody_file, 4)
    else:
        times, note_events, _  = pyjams.util.read_lab(melody_file, 3)        

    end_times = times[1:]
    # hack -- just guess duration of last note from previous note duration
    # if final_t is None:
    #     dt = end_times[-1] - end_times[-2]
    #     final_t = end_times[-1] + dt
    end_times.append(jam.file_metadata.duration)

    note_annot = jam.note.create_annotation()
    note_annot.annotation_metadata.annotator = annotator
    pyjams.util.fill_range_annotation_data(start_times=times, end_times=end_times, labels=note_events, range_annotation=note_annot)


def parse_timing_file(timing_file, jam):
    """ parse a timing data file """

    times, measures = pyjams.util.read_lab(timing_file,2)

    # represent measures as beat annotation. this means that all labels are "1.0", since all events indicate start of measure
    labels = len(times)*[1.0]

    beat_annot = jam.beat.create_annotation()
    pyjams.util.fill_event_annotation_data(times=times, labels=labels, event_annotation=beat_annot)


def create_JAMS(melody_file, harmony_file, timing_file, out_file, annotator, timing_added=True):
    """ convert a JAMS file """

    jam = pyjams.JAMS()
    parse_harmony_clt_file(harmony_file=harmony_file, jam=jam, annotator=annotator, timing_added=timing_added)
    parse_melody_nlt_file(melody_file=melody_file, jam=jam, annotator=annotator, timing_added=timing_added)
    parse_timing_file(timing_file=timing_file, jam=jam)

    # Save JAMS
    with open(out_file, "w") as fp:
        json.dump(jam, fp, indent=2)

def process(in_dir, out_dir):
    """ do the conversion """

    song_map = get_audio_sources_info(os.path.join(in_dir,AUDIO_SOURCES_FILE))



