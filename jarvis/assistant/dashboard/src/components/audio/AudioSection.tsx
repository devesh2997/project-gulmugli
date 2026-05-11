/**
 * AudioSection — composite audio controls for the Controls panel.
 *
 * Contains: volume dial, output device selector, input device selector,
 * bluetooth scanner. These flow vertically without rigid borders —
 * separated by subtle breathing space and section hints.
 *
 * Device-list state (outputs, inputs, override) is refreshed via
 * `actions.fetchDevices()`; the hook polls every 10s so the dashboard
 * picks up plug/unplug events without a manual reload.
 *
 * Tap on a device PINS it (sets the per-side override). The "Reset to
 * auto" button — visible only while any override is active — clears
 * both sides and hands control back to the priority resolver.
 */

import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantStore } from '../../types/assistant'
import { VolumeControl } from './VolumeControl'
import { OutputDevice } from './OutputDevice'
import { InputDevice } from './InputDevice'
import { BluetoothScanner } from './BluetoothScanner'

interface Props {
  store: AssistantStore
}

export function AudioSection({ store }: Props) {
  const { audio, actions } = store
  const requestedRef = useRef(false)
  const hasOverride = audio.override.output !== null || audio.override.input !== null

  // First-paint kick — the hook also polls every 10s, but we want devices
  // visible immediately on mount rather than after the first interval tick.
  useEffect(() => {
    if (!requestedRef.current) {
      requestedRef.current = true
      void actions.fetchDevices()
    }
  }, [actions])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Volume dial */}
      <VolumeControl
        volume={audio.volume}
        onChange={actions.setVolume}
      />

      {/* Reset-to-auto — only visible when something is pinned */}
      <AnimatePresence>
        {hasOverride && (
          <motion.button
            key="reset-override"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 28 }}
            onClick={() => { void actions.clearOverride() }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
            style={{
              alignSelf: 'flex-start',
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '6px 12px',
              fontSize: 10, fontWeight: 600, letterSpacing: 2,
              textTransform: 'uppercase' as const,
              color: 'var(--text-tertiary)',
              background: 'transparent',
              border: '1px solid var(--border-subtle)',
              borderRadius: 12,
              cursor: 'pointer',
            }}
          >
            <span style={{ fontSize: 12, letterSpacing: 0 }}>↺</span>
            Reset to auto
          </motion.button>
        )}
      </AnimatePresence>

      {/* Output devices — only show if we have any */}
      <AnimatePresence>
        {audio.outputs.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              fontSize: 10, fontWeight: 600, letterSpacing: 2,
              textTransform: 'uppercase' as const,
              color: 'var(--text-tertiary)', marginBottom: 10,
            }}>
              Output
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {audio.outputs.map(d => (
                <OutputDevice
                  key={d.name}
                  device={d}
                  onSelect={() => { void actions.pinOutput(d.name) }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Input devices — only show if we have any */}
      <AnimatePresence>
        {audio.inputs.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              fontSize: 10, fontWeight: 600, letterSpacing: 2,
              textTransform: 'uppercase' as const,
              color: 'var(--text-tertiary)', marginBottom: 10,
            }}>
              Input
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {audio.inputs.map(d => (
                <InputDevice
                  key={d.name}
                  device={d}
                  onSelect={() => { void actions.pinInput(d.name) }}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bluetooth */}
      <div>
        <div style={{
          fontSize: 10, fontWeight: 600, letterSpacing: 2,
          textTransform: 'uppercase' as const,
          color: 'var(--text-tertiary)', marginBottom: 10,
        }}>
          Bluetooth
        </div>
        <BluetoothScanner
          scanning={audio.bluetoothScanning}
          devices={audio.bluetoothDevices}
          onScan={actions.btScan}
          onPair={actions.btPair}
          onDisconnect={actions.btDisconnect}
        />
      </div>
    </div>
  )
}
