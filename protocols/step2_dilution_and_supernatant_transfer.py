from opentrons import protocol_api
from opentrons import types
from opentrons.protocol_api import ALL

# Software and robot version requirements: Opentrons App 8.2.0 or later

metadata = {
    'protocolName': 'Step 2: Dilution and Supernatant Transfer to Two 384-Well Plates',
    'author': 'Maria Cardelino + Catherine Mullins + Aryan Patel',
    'description': 'Adds 60 uL water to the C18 384-well plate, then transfers supernatant '
                   'from the intermediate 384-well plate to the C18 and HILIC plates.'
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}

# =============================================================================
# *** USER SETTINGS - EDIT HERE ***
# =============================================================================

NUM_SAMPLE_PLATES = 3       # Must match the value used in Step 1.

RETURN_TIPS_TO_RACK = False  # True:  return every tip to its rack instead of trashing it.
                             #        Use for dry runs, where tips are reused or inspected.
                             # False: drop tips in the trash. Normal setting for real samples.

# --- Supernatant Transfer Settings ---
sup_vol_C18      = 30       # uL to the C18 plate (into 60 uL water -> 2:1 dilution)
sup_vol_HILIC    = 40       # uL to the HILIC plate (undiluted)
sup_asp_depth    = 4.5      # mm above the bottom of the source well. This is the single
                            # most important parameter in the protocol: it sits above the
                            # precipitated protein pellet. Lower values draw protein into
                            # the transfer and contaminate the extract.
sup_blow_height  = 12       # mm above the bottom of the destination well for dispense
sup_airgap       = 5        # uL trailing air gap, aspirated after the supernatant
sup_asp_rate     = 5        # uL/sec - deliberately slow, to preserve transfer fidelity
sup_disp_rate    = 10       # uL/sec   from the shallow 384-well geometry

# --- Solvent Addition Settings (water -> C18 plate) ---
solvent_vol            = 60     # uL per transfer
solvent_airgap         = 10     # uL trailing air gap
solvent_blow_rate      = 800    # uL/sec
solvent_asp_rate       = 40     # uL/sec
solvent_disp_rate      = 120    # uL/sec
solvent_airgap_rate    = 15     # uL/sec (air gap aspiration only)

# =============================================================================
# 96-WELL TO 384-WELL MAPPING
# =============================================================================
# Same quadrant scheme as Step 1: the 96-channel head (9 mm spacing) on a
# 384-well plate (4.5 mm spacing) addresses one of four interleaved 96-well
# quadrants per pickup, named by the anchor well the head lands on.
#
# Because source and destination plates are both 384-well and share the same
# geometry, each quadrant transfers straight across - anchor A1 on the
# intermediate plate goes to anchor A1 on the C18 and HILIC plates - so sample
# identity is preserved by position with no remapping.
#
# One tip rack is consumed per quadrant. The QA/QC quadrant always runs last.
#
#   3 sample racks + QA/QC -> A1, A2, B1 (samples) + B2 (QA/QC): the whole plate
#   2 sample racks + QA/QC -> A1, A2     (samples) + B1 (QA/QC)
#   1 sample rack  + QA/QC -> A1         (sample)  + B1 (QA/QC)

if NUM_SAMPLE_PLATES == 1:
    SOLVENT_DEST_WELLS = ["A1", "B1"]
elif NUM_SAMPLE_PLATES == 2:
    SOLVENT_DEST_WELLS = ["A1", "A2", "B1"]
elif NUM_SAMPLE_PLATES == 3:
    SOLVENT_DEST_WELLS = ["A1", "A2", "B1", "B2"]
else:
    raise ValueError(
        "NUM_SAMPLE_PLATES must be 1, 2, or 3 (got {}).".format(NUM_SAMPLE_PLATES)
    )

# Supernatant sources are the same quadrants that received water.
SUP_SOURCE_WELLS = list(SOLVENT_DEST_WELLS)

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

    temp_mod_b = protocol.load_module('temperature module gen2', 'B1')
    temp_mod_b.set_temperature(4)
    hilic_plate = temp_mod_b.load_labware(
        'thermofisher_384_wellplate_250ul',
        label='HILIC 384-well plate (final, undiluted)')

    temp_mod_c = protocol.load_module('temperature module gen2', 'C1')
    temp_mod_c.set_temperature(4)
    c18_plate = temp_mod_c.load_labware(
        'thermofisher_384_wellplate_250ul',
        label='C18 384-well plate (final, 2:1 diluted)')

    temp_mod_d = protocol.load_module('temperature module gen2', 'D1')
    temp_mod_d.set_temperature(4)
    source_plate = temp_mod_d.load_labware(
        'thermofisher_384_wellplate_250ul',
        label='Intermediate 384-well plate from Step 1 (centrifuged)')

    reservoir_water = protocol.load_labware(
        'nest_1_reservoir_195ml', 'C2',
        label='UHPLC-MS-grade water')

    pipette = protocol.load_instrument(instrument_name="flex_96channel_1000")

    # -------------------------------------------------------------------------
    # Load Tip Racks
    # -------------------------------------------------------------------------
    # All racks are staged on the deck before the run starts.

    # Water tips - 200 uL. Load tips in COLUMNS 1-3 ONLY.
    tiprack_solvent = protocol.load_labware(
        'opentrons_flex_96_tiprack_200ul', 'C3',
        adapter='opentrons_flex_96_tiprack_adapter',
        label='Water tips (200 uL) - 3 COLUMNS ONLY')

    # Supernatant tips - 50 uL FILTER tips, one full rack per quadrant.
    tiprack_sup_1 = protocol.load_labware(
        'opentrons_flex_96_filtertiprack_50ul', 'A1',
        adapter='opentrons_flex_96_tiprack_adapter',
        label='Supernatant tips, quadrant 1 (50 uL filter)')

    tiprack_sup_2 = None
    if NUM_SAMPLE_PLATES >= 2:
        tiprack_sup_2 = protocol.load_labware(
            'opentrons_flex_96_filtertiprack_50ul', 'A2',
            adapter='opentrons_flex_96_tiprack_adapter',
            label='Supernatant tips, quadrant 2 (50 uL filter)')

    tiprack_sup_3 = None
    if NUM_SAMPLE_PLATES == 3:
        tiprack_sup_3 = protocol.load_labware(
            'opentrons_flex_96_filtertiprack_50ul', 'A3',
            adapter='opentrons_flex_96_tiprack_adapter',
            label='Supernatant tips, quadrant 3 (50 uL filter)')

    tiprack_qaqc = protocol.load_labware(
        'opentrons_flex_96_filtertiprack_50ul', 'B3',
        adapter='opentrons_flex_96_tiprack_adapter',
        label='Supernatant tips, QA/QC quadrant (50 uL filter)')

    # -------------------------------------------------------------------------
    # PHASE 1: Water Addition (C18 plate only)
    # -------------------------------------------------------------------------
    # Water goes into the C18 plate before the supernatant, so the extract is
    # delivered into aqueous diluent. The HILIC plate receives no water - that
    # sample stays undiluted.
    #
    # The full 96-channel head picks up tips, but only columns 1-3 are physically
    # loaded. Same tips are used throughout this phase.
    # -------------------------------------------------------------------------

    pipette.configure_nozzle_layout(style=ALL, start="A1", tip_racks=[tiprack_solvent])
    pipette.pick_up_tip(tiprack_solvent)
    pipette.move_to(reservoir_water["A1"].top(20))

    for dest_well in SOLVENT_DEST_WELLS:
        _solvent_addition(pipette, reservoir_water, c18_plate, dest_well,
                          solvent_vol, solvent_blow_rate, solvent_asp_rate,
                          solvent_disp_rate, solvent_airgap_rate, solvent_airgap)
        pipette.move_to(reservoir_water["A1"].top(20), force_direct=True)

    _dispose_tip(pipette, RETURN_TIPS_TO_RACK)

    # -------------------------------------------------------------------------
    # PHASE 2: Supernatant Transfer (intermediate plate -> C18 and HILIC plates)
    # -------------------------------------------------------------------------
    # Each quadrant uses its own filter tip rack. One pickup serves both
    # destinations: C18 first, then HILIC, then the tips are discarded. The
    # QA/QC quadrant always runs last.
    # -------------------------------------------------------------------------

    protocol.pause('Solvent addition complete. Place source 384-well plate in D1 '
                   'and remove seal, then continue.')

    sup_tipracks = [tiprack_sup_1]
    if tiprack_sup_2:
        sup_tipracks.append(tiprack_sup_2)
    if tiprack_sup_3:
        sup_tipracks.append(tiprack_sup_3)
    sup_tipracks.append(tiprack_qaqc)

    pipette.configure_nozzle_layout(style=ALL, start="A1", tip_racks=sup_tipracks)

    for plate_idx, source_well in enumerate(SUP_SOURCE_WELLS):
        _transfer_supernatant(
            pipette, protocol, source_plate, c18_plate, hilic_plate,
            sup_tipracks[plate_idx], source_well,
            sup_vol_C18, sup_vol_HILIC, sup_airgap,
            sup_blow_height, sup_asp_depth,
            sup_asp_rate, sup_disp_rate,
            RETURN_TIPS_TO_RACK
        )

    # Heat-seal both plates immediately after this protocol finishes.

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


def _solvent_addition(pte, reservoir, dest_plate, dest_well, vol,
                      blow_rate, asp_rate, disp_rate, airgap_rate, airgap):
    """One aspiration from the water reservoir, one dispense into dest_well of the
    384-well C18 plate."""

    pte.flow_rate.blow_out = blow_rate
    pte.flow_rate.aspirate = asp_rate
    pte.flow_rate.dispense = disp_rate

    pte.aspirate(31)                                              # leading air plug
    pte.aspirate(vol, reservoir["A1"].bottom(2))
    pte.move_to(reservoir["A1"].top(20), force_direct=True)

    pte.flow_rate.aspirate = airgap_rate
    pte.aspirate(airgap)                                          # trailing air gap

    pte.move_to(dest_plate[dest_well].top(5), force_direct=True)
    # Water + trailing air gap + 10 uL of the leading plug.
    pte.dispense(vol + 10 + airgap, dest_plate[dest_well].top(-10))

    # Blow out the remaining plug against the well wall to shed droplets.
    pte.move_to(dest_plate[dest_well].top(-1).move(types.Point(x=1)), force_direct=True)
    pte.flow_rate.dispense = 1000
    pte.dispense(20)
    pte.move_to(dest_plate[dest_well].top(5), force_direct=True)


def _transfer_supernatant(pte, ctx, source_plate, c18_plate, hilic_plate,
                          tiprack, source_well,
                          vol_C18, vol_HILIC, airgap,
                          blow_height, asp_depth,
                          asp_rate, disp_rate,
                          return_tips_to_rack):
    """Pick up filter tips and transfer supernatant from one quadrant of the source
    plate to the same quadrant of the C18 plate, then the HILIC plate, on a single
    set of tips.

    Descent to the aspiration height is speed-limited (speed=10) so the approach
    does not disturb the protein pellet before aspiration begins."""

    pte.flow_rate.aspirate = asp_rate
    pte.flow_rate.dispense = disp_rate

    pte.pick_up_tip(tiprack)

    # --- C18 plate (diluted 2:1 into the water already in the well) ---
    pte.move_to(source_plate[source_well].top())
    pte.flow_rate.aspirate = 1000
    pte.aspirate(15)                                              # leading air plug
    pte.move_to(source_plate[source_well].bottom(asp_depth), speed=10)
    pte.flow_rate.aspirate = asp_rate
    pte.aspirate(vol_C18, source_plate[source_well].bottom(asp_depth))
    pte.move_to(source_plate[source_well].top(5))
    pte.aspirate(airgap)                                          # trailing air gap

    pte.move_to(c18_plate[source_well].top(5), force_direct=True)
    pte.dispense(vol_C18 + airgap, c18_plate[source_well].bottom(blow_height))
    pte.move_to(c18_plate[source_well].bottom(3), speed=10)
    pte.move_to(c18_plate[source_well].top(-10), speed=10)
    ctx.delay(2)
    pte.flow_rate.dispense = 1000
    pte.dispense(14)                                              # blow out the 15 uL plug

    # Tip-touch against the well wall to shed the hanging droplet.
    pte.move_to(c18_plate[source_well].top(-3))
    pte.move_to(c18_plate[source_well].top(-3).move(types.Point(x=1.5)), speed=8)
    pte.move_to(c18_plate[source_well].top(5))

    # --- HILIC plate (undiluted) ---
    pte.move_to(source_plate[source_well].top(5), force_direct=True)
    pte.flow_rate.aspirate = 1000
    pte.aspirate(4)                                               # leading air plug
    pte.move_to(source_plate[source_well].bottom(asp_depth), speed=10)
    pte.flow_rate.aspirate = asp_rate
    pte.aspirate(vol_HILIC, source_plate[source_well].bottom(asp_depth))
    pte.move_to(source_plate[source_well].top(5))
    pte.aspirate(airgap)                                          # trailing air gap

    pte.move_to(hilic_plate[source_well].top(5), force_direct=True)
    pte.flow_rate.dispense = disp_rate
    pte.dispense(vol_HILIC + airgap, hilic_plate[source_well].bottom(blow_height))
    pte.move_to(hilic_plate[source_well].bottom(3), speed=10)
    pte.move_to(hilic_plate[source_well].top(-10), speed=10)
    ctx.delay(2)
    pte.flow_rate.dispense = 1000
    pte.dispense(4)                                               # blow out the 4 uL plug

    pte.move_to(hilic_plate[source_well].top(-3))
    pte.move_to(hilic_plate[source_well].top(-3).move(types.Point(x=1.5)), speed=8)
    pte.move_to(hilic_plate[source_well].top(5))

    _dispose_tip(pte, return_tips_to_rack)
    pte.reset_tipracks()
