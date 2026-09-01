# Ubiquitous Language

## Bridge

The user-owned component that connects Herdr agent activity to a duckyPad and routes supported physical-key selections back to Herdr. It has no user interface.

## Herdr Mode

A duckyPad operating mode in which supported primary-key input is reserved for Herdr selection and its LED frame is supplied by the Bridge. It is distinct from Profile Mode.

## Profile Mode

The existing duckyPad mode in which a profile's DPDS macros and key behaviours are active.

## Mapping

A user-configured relationship between one supported duckyPad primary-key slot and one Herdr agent target within a workspace. A Mapping is invalid when its target leaves that workspace.

## Agent Target

The pane that currently hosts the selected Herdr agent, identified within its workspace. It is the thing a Mapping selects; an agent display name alone is not an Agent Target.

## Capability

A hardware and firmware feature that the Bridge can verify before enabling a mode. Unsupported or unverifiable Capability is unavailable, not emulated.

## Device Format

The profile, ZIP, DPDS, DSB, and related data that a duckyPad and existing user workflow can exchange directly.

## Application State

The versioned, user-local information used to configure the Configurator and Bridge that is not part of the Device Format.

## Agent Status

The current effective Herdr state of an Agent Target: working, blocked, idle, done, or unknown.

## LED Presentation

The visible state of a supported Mapping after its Agent Status, capability, connection health, and temporary feedback have been resolved by precedence.
