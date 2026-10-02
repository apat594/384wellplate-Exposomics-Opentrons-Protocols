from opentrons import protocol_api
from opentrons import types
from opentrons.protocol_api import ALL

# Software and robot version requirements: Opentrons App 8.2.0 or later

metadata = {
    'protocolName': 'Step 1: Extraction Solvent Addition and Sample Aliquoting',
    'author': 'Maria Cardelino + Catherine Mullins + Aryan Patel',
    'description': 'Adds 90 uL extraction solvent (60:40 MeOH/ACN + internal standards) '
                   'and 30 uL plasma from 96-well Matrix racks into a 384-well plate.'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

# =============================================================================
# *** USER SETTINGS - EDIT HERE ***
# =============================================================================

NUM_SAMPLE_PLATES = 3       # 1, 2, or 3 sample racks. The QA/QC rack runs after.
                            # 3 racks + QA/QC fills all 384 wells (288 study samples
                            # + up to 96 QA/QC wells).

RETURN_TIPS_TO_RACK = False  # True:  return every tip to its rack instead of trashing it.
                             #        Use for dry runs, where tips are reused or inspected.
                             # False: drop tips in the trash. Normal setting for real samples.

# --- Sample Aliquot Settings ---
sample_vol       = 30       # uL of plasma per transfer
sample_asp_depth = 3        # mm above the bottom of the sample tube. Match to the
                            # available sample volume and matrix; 3-6 mm is the
                            # working range (3 mm for low-volume specimens).
qaqc_asp_depth   = 3        # mm above the bottom of the QA/QC tube
blow_height      = 12       # mm above the bottom of the 384-well plate for dispense
sample_blow_rate = 200      # uL/sec
sample_asp_rate  = 10       # uL/sec
sample_disp_rate = 20       # uL/sec

# --- Extraction Solvent (ES) Settings ---
ES_vol            = 90      # uL per transfer
ES_airgap         = 10      # uL trailing air gap, aspirated after the solvent
ES_blow_rate      = 800     # uL/sec
ES_asp_rate       = 92      # uL/sec
ES_disp_rate      = 40      # uL/sec
ES_airgap_rate    = 15      # uL/sec (air gap aspiration only)
ES_asp_depth      = 2       # mm above the reservoir bottom, fixed for all aspirations

# --- Reservoir X Offset ---
# The 96-channel tip columns are spaced 9 mm apart. With 3 columns of tips they
# span 18 mm in X (columns at x=0, +9, +18 relative to the A1 nozzle centre).
# The reservoir well (opentrons_tough_4_reservoir_72ml) is 26.43 mm wide in X.
# Shifting -9 mm centres the middle tip column on the well centre, keeping all
# three columns safely inside the well. 
# This can be adjusted for a different reservoir geometry.
RESERVOIR_X_OFFSET = -9     # mm

# =============================================================================
# 96-WELL TO 384-WELL MAPPING
# =============================================================================
# The 96-channel head has 9 mm tip spacing; the 384-well plate has 4.5 mm well
# spacing. One tip pickup therefore addresses every other row and every other
# column - i.e. one of four interleaved 96-well quadrants of the 384-well plate.
# Each quadrant is named by the well the head lands on ("anchor well"):
#
#   anchor A1 -> odd rows,  odd columns      anchor A2 -> odd rows,  even columns
#   anchor B1 -> even rows, odd columns      anchor B2 -> even rows, even columns
#
# Sample racks fill quadrants in order (A1, then A2, then B1), and the QA/QC
# rack always occupies quadrant B2, whatever the sample rack count. Keeping
# QA/QC in a fixed quadrant means the QA/QC plate map does not change between
# runs of different sizes. Because quadrants are interleaved, study samples and
# QA/QC materials are distributed across the whole plate rather than blocked
# together - this is what allows plate position effects to be evaluated after
# acquisition.
#
# Extraction solvent is delivered with only 3 columns of tips at a time, so it
# needs more anchor wells than the sample transfers: each ES anchor covers three
# 384-plate columns (e.g. A1 -> columns 1, 3, 5).
#
# QA/QC capacity:
# ES_DEST_WELLS decides which wells receive extraction solvent, so the number of
# QA/QC materials a run can hold is set by how many B-row anchors are listed.
# Every configuration below delivers solvent to the full QA/QC quadrant, so up
# to 96 QA/QC materials are supported by default. The number and composition of
# QA/QC materials is a per-batch decision, so this is an upper limit and not a
# requirement - a partially filled QA/QC rack is expected, and wells that
# receive solvent but no sample are simply left unused.
#
# To reduce solvent consumption when fewer QA/QC materials are needed, remove
# anchors from the end of the QA/QC group. Because QA/QC is always quadrant B2,
# that group is the same in every configuration. Each anchor covers 24 wells
# (3 columns of the 384-well plate, equal to 2 columns of the source rack):
#
#   B2, B8, B14, B20  -> 96 QA/QC wells (default)
#   B2, B8, B14       -> 72
#   B2, B8            -> 48
#   B2                -> 24
#
# Solvent must always reach every well that will receive sample, so never remove
# an anchor covering a QA/QC source position that will be filled.
#
# To use a different layout, override ES_DEST_WELLS / SAMPLE_DEST_WELLS below.

if NUM_SAMPLE_PLATES == 1:
    ES_DEST_WELLS     = ["A1", "A7", "A13", "A19",
                         "B2", "B8", "B14", "B20"]
    SAMPLE_DEST_WELLS = ["A1"]
    QAQC_DEST_WELL    = "B2"
elif NUM_SAMPLE_PLATES == 2:
    ES_DEST_WELLS     = ["A1", "A2", "A7", "A8", "A13", "A14", "A19", "A20",
                         "B2", "B8", "B14", "B20"]
    SAMPLE_DEST_WELLS = ["A1", "A2"]
    QAQC_DEST_WELL    = "B2"
elif NUM_SAMPLE_PLATES == 3:
    ES_DEST_WELLS     = ["A1", "A2", "A7", "A8", "A13", "A14", "A19", "A20",
                         "B1", "B2", "B7", "B8", "B13", "B14", "B19", "B20"]
    SAMPLE_DEST_WELLS = ["A1", "A2", "B1"]
    QAQC_DEST_WELL    = "B2"
else:
    raise ValueError(
        "NUM_SAMPLE_PLATES must be 1, 2, or 3 (got {}).".format(NUM_SAMPLE_PLATES)
    )

# =============================================================================
# END USER SETTINGS
# =============================================================================


def run(protocol: protocol_api.ProtocolContext):

    protocol.set_rail_lights(True)
    protocol.load_trash_bin("D3")

    # -------------------------------------------------------------------------
    # Load Modules and Labware
    # -------------------------------------------------------------------------
    # All three temperature modules hold at 4 C for the duration of the run.

    temp_mod_c = protocol.load_module('temperature module gen2', "C1")
    temp_mod_c.set_temperature(4)
    wellplate_dest = temp_mod_c.load_labware(
        'thermofisher_384_wellplate_250ul',
        label='Intermediate 384-well plate')

    temp_mod_b = protocol.load_module('temperature module gen2', "B1")
    temp_mod_b.set_temperature(4)
    reservoir = temp_mod_b.load_labware(
        'opentrons_tough_4_reservoir_72ml',
        label='Extraction solvent - fill well A1')

    temp_mod_d = protocol.load_module('temperature module gen2', "D1")
    temp_mod_d.set_temperature(4)
    wellplate_source = temp_mod_d.load_labware(
        'matrix96well_96_tuberack_1000ul',
        label='Sample 96-well Matrix rack')

    pipette = protocol.load_instrument(instrument_name="flex_96channel_1000")

    # -------------------------------------------------------------------------
    # Load Tip Racks
    # -------------------------------------------------------------------------

    # Extraction solvent tips - 200 uL. Load tips in COLUMNS 1-3 ONLY.
    tiprack_es = protocol.load_labware(
        "opentrons_flex_96_tiprack_200ul", "C3",
        adapter="opentrons_flex_96_tiprack_adapter",
        label="Extraction solvent tips (200 uL) - 3 COLUMNS ONLY")

    # Sample tips - 50 uL, one full rack per sample rack.
    tiprack_sample_1 = protocol.load_labware(
        "opentrons_flex_96_tiprack_50ul", "A1",
        adapter="opentrons_flex_96_tiprack_adapter",
        label="Sample rack 1 tips (50 uL)")

    tiprack_sample_2 = None
    if NUM_SAMPLE_PLATES >= 2:
        tiprack_sample_2 = protocol.load_labware(
            "opentrons_flex_96_tiprack_50ul", "A2",
            adapter="opentrons_flex_96_tiprack_adapter",
            label="Sample rack 2 tips (50 uL)")

    tiprack_sample_3 = None
    if NUM_SAMPLE_PLATES == 3:
        tiprack_sample_3 = protocol.load_labware(
            "opentrons_flex_96_tiprack_50ul", "A3",
            adapter="opentrons_flex_96_tiprack_adapter",
            label="Sample rack 3 tips (50 uL)")

    tiprack_qaqc = protocol.load_labware(
        "opentrons_flex_96_tiprack_50ul", "B3",
        adapter="opentrons_flex_96_tiprack_adapter",
        label="QA/QC rack tips (50 uL)")

    # -------------------------------------------------------------------------
    # PHASE 1: Extraction Solvent Addition
    # -------------------------------------------------------------------------
    # Solvent goes in before sample, so the plasma is delivered into solvent and
    # protein precipitation begins immediately.
    #
    # The full 96-channel head picks up tips, but only columns 1-3 are physically
    # loaded, so three tip columns aspirate and dispense at a time. One aspiration
    # from the reservoir feeds one dispense per anchor well in ES_DEST_WELLS. The
    # same tips are used throughout and are pre-wetted three times first.
    # -------------------------------------------------------------------------

    pipette.configure_nozzle_layout(style=ALL, start="A1", tip_racks=[tiprack_es])
    pipette.pick_up_tip(tiprack_es)

    for _ in range(3):
        _prewet(pipette, reservoir, ES_vol, ES_blow_rate, ES_asp_rate,
                ES_disp_rate, ES_airgap_rate, ES_airgap, RESERVOIR_X_OFFSET)

    for i, dest_well in enumerate(ES_DEST_WELLS):
        last = (i == len(ES_DEST_WELLS) - 1)
        _es_addition(pipette, reservoir, wellplate_dest, dest_well, ES_vol,
                     ES_blow_rate, ES_asp_rate, ES_disp_rate, ES_airgap_rate,
                     ES_airgap, RESERVOIR_X_OFFSET, ES_asp_depth, last=last)

    _dispose_tip(pipette, RETURN_TIPS_TO_RACK)

    # -------------------------------------------------------------------------
    # PHASE 2: Sample Aliquoting
    # -------------------------------------------------------------------------
    # Each sample rack uses its own tip rack and its own destination quadrant.
    # The protocol pauses between racks so only one rack is uncapped and off ice
    # at a time. The QA/QC rack always runs last.
    # -------------------------------------------------------------------------

    protocol.pause('Place uncapped samples in D1, then continue.')

    sample_tipracks = [tiprack_sample_1]
    if tiprack_sample_2:
        sample_tipracks.append(tiprack_sample_2)
    if tiprack_sample_3:
        sample_tipracks.append(tiprack_sample_3)

    pipette.configure_nozzle_layout(
        style=ALL, start="A1",
        tip_racks=sample_tipracks + [tiprack_qaqc]
    )

    for plate_idx in range(NUM_SAMPLE_PLATES):
        _aliquot(
            pipette, protocol, wellplate_source, wellplate_dest,
            sample_tipracks[plate_idx], tiprack_es,
            SAMPLE_DEST_WELLS[plate_idx],
            sample_vol, sample_asp_depth, blow_height,
            sample_blow_rate, sample_asp_rate, sample_disp_rate,
            RETURN_TIPS_TO_RACK
        )
        protocol.pause('Replace sample plate, then resume.')

    # QA/QC rack
    _aliquot(
        pipette, protocol, wellplate_source, wellplate_dest,
        tiprack_qaqc, tiprack_es, QAQC_DEST_WELL,
        sample_vol, qaqc_asp_depth, blow_height,
        sample_blow_rate, sample_asp_rate, sample_disp_rate,
        RETURN_TIPS_TO_RACK
    )

    pipette.move_to(tiprack_es["A1"].top(50))

    # Heat-seal the plate immediately after this protocol finishes.

    # END PROTOCOL


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _dispose_tip(pte, return_tips_to_rack):
    """Return the tip to its rack (dry run) or drop it in the trash (normal run),
    per RETURN_TIPS_TO_RACK."""
    if return_tips_to_rack:
        pte.return_tip()
    else:
        pte.drop_tip()


def _prewet(pte, reservoir, vol, blow_rate, asp_rate, disp_rate,
            airgap_rate, airgap, x_offset):
    """Pre-wet the tips by aspirating solvent and dispensing it straight back into
    the reservoir. Volatile organic solvent otherwise evaporates inside a dry tip
    and the first few deliveries come up short.

    x_offset centres the three tip columns inside the reservoir well. Aspiration
    is at bottom(8) - shallow, just enough to wet the tips."""

    pte.flow_rate.blow_out = blow_rate
    pte.flow_rate.aspirate = asp_rate
    pte.flow_rate.dispense = disp_rate

    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)))
    pte.aspirate(31)                                         # leading air plug
    pte.aspirate(vol, reservoir["A1"].bottom(8).move(types.Point(x=x_offset)))
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)

    pte.flow_rate.aspirate = airgap_rate
    pte.aspirate(airgap)

    pte.move_to(reservoir["A1"].top(-2).move(types.Point(x=x_offset)), force_direct=True)
    # Push back the solvent, the trailing air gap, and 10 uL of the leading plug.
    pte.dispense(vol + 10 + airgap)
    pte.flow_rate.dispense = 1000
    pte.dispense(20)                                         # blow out the remaining plug


def _es_addition(pte, reservoir, dest_plate, dest_well, vol,
                 blow_rate, asp_rate, disp_rate, airgap_rate, airgap, x_offset, asp_depth,
                 last=False):
    """One aspiration from the reservoir (B1), one dispense into dest_well of the
    384-well plate (C1).

    x_offset centres the three tip columns inside the reservoir well.

    Travel height is the absolute Z of reservoir["A1"].top(2). The taller labware
    sets the reference, so every lateral move happens at one fixed absolute Z and
    the head never travels diagonally when crossing between B1 (tall reservoir)
    and C1 (short 384-well plate). All movements are strictly single-axis:
      - Z only:  force_direct=True
      - XY only: both endpoints share the reservoir top(2) absolute Z

    last=True skips the return-to-reservoir move after the final dispense; the
    pipette goes straight to tip disposal in run()."""

    pte.flow_rate.blow_out = blow_rate
    pte.flow_rate.aspirate = asp_rate
    pte.flow_rate.dispense = disp_rate

    # Absolute Z travel height - 2 mm above the reservoir top (the taller labware)
    travel_z = reservoir["A1"].top(2).point.z

    # --- Aspirate from the reservoir (B1) ---
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)
    pte.aspirate(31)                                                                    # leading air plug
    pte.aspirate(vol, reservoir["A1"].bottom(asp_depth).move(types.Point(x=x_offset)))  # descend, aspirate
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)
    pte.flow_rate.aspirate = airgap_rate
    pte.aspirate(airgap)                                                                # trailing air gap
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)

    # --- B1 -> C1: purely lateral move at travel height ---
    dest_xy = dest_plate[dest_well].top().point
    lateral_dest = types.Location(types.Point(x=dest_xy.x, y=dest_xy.y, z=travel_z), None)
    pte.move_to(lateral_dest, force_direct=True)

    # --- Descend into the destination plate (C1) and dispense ---
    pte.move_to(dest_plate[dest_well].top(-3), force_direct=True)
    # Solvent + trailing air gap + 10 uL of the leading plug.
    pte.dispense(vol + 10 + airgap)

    # Blow out above the liquid and tip-touch to shed hanging droplets. Both
    # happen before the tip contacts the well wall, so nothing is re-aspirated
    # and nothing is carried into the next well.
    pte.move_to(dest_plate[dest_well].top(-0.5), force_direct=True)
    pte.move_to(dest_plate[dest_well].top(-0.5).move(types.Point(x= 1)), force_direct=True)
    pte.move_to(dest_plate[dest_well].top(-0.5).move(types.Point(x=-1)), force_direct=True)
    pte.flow_rate.dispense = 1000
    pte.dispense(20)                                                                    # blow out remaining plug

    if last:
        return  # _dispose_tip() is called in run(); skip the return-to-reservoir path

    # --- Rise to travel height, then move laterally back to the reservoir ---
    rise_back = types.Location(types.Point(x=dest_xy.x, y=dest_xy.y, z=travel_z), None)
    pte.move_to(rise_back, force_direct=True)
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)
    pte.move_to(reservoir["A1"].top(2).move(types.Point(x=x_offset)), force_direct=True)


def _aliquot(pte, ctx, source, dest, tiprack, ref_tiprack, dest_well,
             vol, asp_depth, blow_height, blow_rate, asp_rate, disp_rate,
             return_tips_to_rack):
    """Pick up tips, aspirate plasma from a 96-well Matrix rack, and dispense into
    one quadrant of the 384-well plate. Used for both sample racks and the QA/QC
    rack - they differ only in aspiration depth and destination quadrant."""

    pte.flow_rate.blow_out = blow_rate
    pte.flow_rate.aspirate = asp_rate
    pte.flow_rate.dispense = disp_rate

    pte.pick_up_tip(tiprack)

    pte.flow_rate.aspirate = 1000
    pte.aspirate(20, source["A1"].top())                     # leading air plug
    pte.flow_rate.aspirate = asp_rate
    pte.aspirate(vol, source["A1"].bottom(asp_depth))
    ctx.delay(4)                                             # let the viscous plasma
                                                             # column settle in the tip
                                                             # before the head moves
    pte.move_to(source["A1"].top(5), force_direct=True)

    pte.move_to(dest[dest_well].top(25), force_direct=True)
    pte.dispense(vol, dest[dest_well].bottom(blow_height))

    # Withdraw, return to the dispense height, and blow out 19 uL of the 20 uL
    # leading plug to clear plasma clinging to the tip.
    pte.move_to(dest[dest_well].top(-10.5))
    pte.move_to(dest[dest_well].bottom(blow_height))
    ctx.delay(2)
    pte.flow_rate.dispense = 1000
    pte.dispense(19)

    _dispose_tip(pte, return_tips_to_rack)
    pte.reset_tipracks()
    pte.move_to(ref_tiprack["A1"].top(50))
