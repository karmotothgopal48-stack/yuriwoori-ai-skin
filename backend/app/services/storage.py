"""
NO SELFIE STORAGE: scan photos are never written anywhere (disk, database, S3). They are checked and analysed in
memory only (endpoints/scans.py); scan_frames.storage_key is "not-stored" for every new frame.

All that is left here is the folder older scans used to write photos to, so scripts/purge_legacy_selfies.py can
remove what they left behind. Nothing in the app writes to it.
"""

import os

# Where scans made before photos stopped being stored kept them: app/uploads/<scan id>/<angle>.jpg
UPLOAD_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
