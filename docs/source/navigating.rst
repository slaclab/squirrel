Navigating
==========

The left side of the app contains the control panel, which has buttons to open
three pages:

Snapshot Table
--------------
This table lists all snapshots in reverse chronological order. Each snapshot has
a timestamp, a title, and values for any meta-PVs.

Above the table are controls for filtering rows in the table by date range,
title, or meta-PV value. To filter by Meta PV value, click the button labeled
"Filter", then select the desired PV, operator, and reference value.

Double-clicking on a row will open the snapshot, displaying saved values for all
PVs. Live values will also be displayed next to the saved values, and they will
be highlighted if they differ from the saved value by more than their tolerance.

PV Table
--------
This table shows which PVs are tracked by the app, including each PV's setpoint,
readback, and tags. Double-clicking a row will open a pop-up displaying
additional information, including a description and EPICS tolerances.

Above the table are controls for filtering by PV name or by tags.

In admin mode, the page will have a button for adding PVs, rows will have a
delete button, and fields in the PV pop-up will be editable

Tag Configuration
-----------------
This page contains a list of tag groups, with each group showing its name, its
description, and how many tags it contains. Double-clicking a group will open a
pop-up that additionally lists all of the tags in the group.

In admin mode, the page will have a button for adding new tag groups, each group
row will have a delete button, and each pop-up will be editable.
