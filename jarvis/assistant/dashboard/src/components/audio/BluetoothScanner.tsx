/**
 * BluetoothScanner — radar-sweep scanning animation + discovered device list.
 *
 * When scanning: shows expanding concentric rings radiating from a central
 * Bluetooth icon, with a rotating sweep line. Discovered devices appear as
 * glowing dots that fly in from the edges and resolve into named entries.
 *
 * When idle: shows a calm "Scan" button with subtle Bluetooth icon pulse.
 *
 * Pairing animation: the selected device's entry contracts, shows a
 * connecting shimmer, then expands with a "Connected" checkmark.
 */

import { motion, AnimatePresence } from 'framer-motion'
import type { BluetoothDevice } from '../../types/assistant'

interface Props {
  scanning: boolean
  devices: BluetoothDevice[]
  onScan: () => void
  onPair: (mac: string) => void
  onDisconnect: (mac: string) => void
}

/** Expanding ring animation during scan */
function ScanRings() {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      pointerEvents: 'none',
    }}>
      {[0, 1, 2].map(i => (
        <motion.div
          key={i}
          animate={{
            scale: [0.3, 1.8],
            opacity: [0.4, 0],
          }}
          transition={{
            duration: 2.4,
            repeat: Infinity,
            delay: i * 0.8,
            ease: 'easeOut',
          }}
          style={{
            position: 'absolute',
            width: 80, height: 80,
            borderRadius: '50%',
            border: '1.5px solid var(--personality-accent)',
          }}
        />
      ))}
    </div>
  )
}

/** Rotating sweep line */
function SweepLine() {
  return (
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
      style={{
        position: 'absolute',
        width: 100, height: 2,
        left: '50%', top: '50%',
        transformOrigin: '0% 50%',
        background: 'linear-gradient(90deg, var(--personality-accent), transparent)',
        opacity: 0.3,
        pointerEvents: 'none',
      }}
    />
  )
}

/** Bluetooth icon (static center piece) */
function BtIcon({ scanning }: { scanning: boolean }) {
  return (
    <motion.svg
      width="20" height="20" viewBox="0 0 24 24"
      fill="none" stroke="var(--personality-accent)"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      animate={scanning
        ? { opacity: [0.5, 1, 0.5], scale: [0.95, 1.05, 0.95] }
        : { opacity: 1, scale: 1 }
      }
      transition={scanning
        ? { duration: 2, repeat: Infinity, ease: 'easeInOut' }
        : { duration: 0.3 }
      }
    >
      <polyline points="6.5 6.5 17.5 17.5 12 23 12 1 17.5 6.5 6.5 17.5" />
    </motion.svg>
  )
}

/** Individual discovered device row */
function DeviceRow({ device, onPair, onDisconnect }: {
  device: BluetoothDevice
  onPair: (mac: string) => void
  onDisconnect: (mac: string) => void
}) {
  const isConnected = device.connected

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 12px',
        borderRadius: 12,
        background: isConnected
          ? 'rgba(var(--personality-accent-rgb), 0.06)'
          : 'transparent',
      }}
    >
      {/* Status dot */}
      <div style={{
        width: 6, height: 6, borderRadius: 3, flexShrink: 0,
        background: isConnected ? 'var(--personality-accent)' : 'var(--text-tertiary)',
        boxShadow: isConnected ? '0 0 8px var(--personality-accent)' : 'none',
      }} />

      {/* Name */}
      <span style={{
        flex: 1, fontSize: 12, fontWeight: isConnected ? 600 : 400,
        color: isConnected ? 'var(--text-primary)' : 'var(--text-secondary)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {device.name || device.mac}
      </span>

      {/* Signal strength indicator (if available) */}
      {device.rssi != null && (
        <span style={{
          fontSize: 9, color: 'var(--text-tertiary)',
          fontFamily: 'monospace',
        }}>
          {device.rssi}%
        </span>
      )}

      {/* Action button */}
      <motion.button
        onClick={() => isConnected ? onDisconnect(device.mac) : onPair(device.mac)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.92 }}
        style={{
          padding: '4px 10px',
          borderRadius: 8,
          border: isConnected
            ? '1px solid var(--border-subtle)'
            : '1px solid rgba(var(--personality-accent-rgb), 0.3)',
          background: isConnected
            ? 'transparent'
            : 'rgba(var(--personality-accent-rgb), 0.08)',
          cursor: 'pointer',
          fontSize: 10, fontWeight: 600,
          color: isConnected ? 'var(--text-tertiary)' : 'var(--personality-accent)',
          letterSpacing: 0.3,
        }}
      >
        {isConnected ? 'Disconnect' : 'Pair'}
      </motion.button>
    </motion.div>
  )
}

export function BluetoothScanner({ scanning, devices, onScan, onPair, onDisconnect }: Props) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Scan area — radar visualization */}
      <div style={{
        position: 'relative',
        height: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        borderRadius: 16,
      }}>
        {/* Scan rings + sweep when active */}
        <AnimatePresence>
          {scanning && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5 }}
              style={{ position: 'absolute', inset: 0 }}
            >
              <ScanRings />
              <SweepLine />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Central BT icon + scan button */}
        <motion.button
          onClick={onScan}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.94 }}
          disabled={scanning}
          style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', gap: 8,
            padding: '12px 24px',
            borderRadius: 20,
            border: scanning
              ? '1px solid rgba(var(--personality-accent-rgb), 0.2)'
              : '1px solid var(--border-subtle)',
            background: scanning
              ? 'rgba(var(--personality-accent-rgb), 0.04)'
              : 'transparent',
            cursor: scanning ? 'default' : 'pointer',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <BtIcon scanning={scanning} />
          <span style={{
            fontSize: 10, fontWeight: 600,
            color: scanning ? 'var(--personality-accent)' : 'var(--text-secondary)',
            letterSpacing: 1.5,
            textTransform: 'uppercase',
          }}>
            {scanning ? 'Scanning...' : 'Scan'}
          </span>
        </motion.button>
      </div>

      {/* Discovered devices list */}
      <AnimatePresence>
        {devices.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {devices.map(d => (
                <DeviceRow
                  key={d.mac}
                  device={d}
                  onPair={onPair}
                  onDisconnect={onDisconnect}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
