/**
 * AudioSection — composite audio controls for the Controls panel.
 *
 * Contains: volume dial, output device selector, bluetooth scanner.
 * These flow vertically without rigid borders — separated by subtle
 * breathing space and section hints.
 */

import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { AssistantStore } from '../../types/assistant'
import { VolumeControl } from './VolumeControl'
import { OutputDevice } from './OutputDevice'
import { BluetoothScanner } from './BluetoothScanner'

interface Props {
  store: AssistantStore
}

export function AudioSection({ store }: Props) {
  const { audio, actions } = store
  const requestedRef = useRef(false)

  // Request output list once on mount
  useEffect(() => {
    if (!requestedRef.current) {
      requestedRef.current = true
      actions.listOutputs()
    }
  }, [actions])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Volume dial */}
      <VolumeControl
        volume={audio.volume}
        onChange={actions.setVolume}
      />

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
                  onSelect={() => actions.setOutput(d.name)}
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
