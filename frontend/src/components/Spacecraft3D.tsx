"use client";

import React, { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars, Html } from "@react-three/drei";
import * as THREE from "three";
import { Telemetry, ActiveEvent } from "../hooks/useWebSocket";

interface SpacecraftProps {
  telemetry: Telemetry | null;
  state: string;
  activeEvents: ActiveEvent[];
}

function SpacecraftModel({ telemetry, state, activeEvents }: SpacecraftProps) {
  const groupRef = useRef<THREE.Group>(null);
  const solarPanelRef = useRef<THREE.Group>(null);
  const dishRef = useRef<THREE.Group>(null);
  
  // Anomaly-specific refs
  const stormRef = useRef<THREE.Mesh>(null);
  const lightGreenRef = useRef<THREE.Mesh>(null);
  const lightRedRef = useRef<THREE.Mesh>(null);

  const fuel = telemetry?.fuel ?? 100;
  const power = telemetry?.power ?? 100;
  const health = telemetry?.health ?? 100;

  // Detect active hazards
  const isSolarStorm = activeEvents.some(e => e.event_type === "Solar Storm");
  const isFuelLeak = activeEvents.some(e => e.event_type === "Fuel Leak");
  const isCommLoss = activeEvents.some(e => e.event_type === "Communication Loss");
  const isThrusterFail = activeEvents.some(e => e.event_type === "Thruster Failure");
  const isMeteorImpact = activeEvents.some(e => e.event_type === "Micrometeorite Impact");
  const isRadiation = activeEvents.some(e => e.event_type === "Radiation Burst");
  
  const isEmergency = state === "Emergency" || activeEvents.some(e => e.severity === "CRITICAL");
  const isEngineFiring = (state === "Launch" || state === "Maneuver") && !isEmergency;

  useFrame((stateFrame) => {
    const elapsed = stateFrame.clock.getElapsedTime();

    // Gentle floating and overall Y-rotation (normal or wobbling during emergency/drift)
    if (groupRef.current) {
      const wobbleSpeed = isEmergency ? 1.5 : 0.25;
      const wobbleAmp = isEmergency ? 0.04 : 0.01;
      
      groupRef.current.rotation.y = elapsed * 0.025;
      groupRef.current.position.y = Math.sin(elapsed * 0.3) * 0.12;
      
      // Attitude drift wobbling
      groupRef.current.rotation.x = Math.sin(elapsed * wobbleSpeed) * wobbleAmp;
      groupRef.current.rotation.z = Math.cos(elapsed * wobbleSpeed) * wobbleAmp;
    }

    // Solar panels rotation
    if (solarPanelRef.current) {
      solarPanelRef.current.rotation.x = Math.sin(elapsed * 0.08) * 0.04;
    }

    // Gentle spin on the bow communication dish (stuttering if comm is lost)
    if (dishRef.current) {
      if (isCommLoss) {
        dishRef.current.rotation.z = Math.floor(elapsed * 4) * 0.1; // jittering rotation
      } else {
        dishRef.current.rotation.z = elapsed * 0.12;
      }
    }

    // Blinking nav lights
    const blink = Math.sin(elapsed * 5) * 0.5 + 0.5;
    if (lightGreenRef.current) {
      (lightGreenRef.current.material as THREE.MeshBasicMaterial).opacity = isCommLoss ? 0.1 : blink;
    }
    if (lightRedRef.current) {
      (lightRedRef.current.material as THREE.MeshBasicMaterial).opacity = isEmergency ? 1.0 : (isCommLoss ? 0.1 : 1 - blink);
    }

    // Rotate storm particle shell
    if (stormRef.current && isSolarStorm) {
      stormRef.current.rotation.y = elapsed * 0.4;
      stormRef.current.rotation.x = elapsed * 0.2;
    }
  });

  // Color dynamics based on telemetry values
  let alertEmissive = "#000000";
  let alertIntensity = 0;
  if (isEmergency) {
    alertEmissive = "#dc2626";
    alertIntensity = 0.5;
  } else if (isRadiation) {
    alertEmissive = "#10b981"; // green glow during radiation burst
    alertIntensity = 0.35;
  }

  let healthColor = "#059669"; // emerald-600
  if (health < 30) {
    healthColor = "#dc2626"; // red-600
  } else if (health < 75) {
    healthColor = "#ca8a04"; // yellow-600
  }

  const powerGlowIntensity = power / 100;
  const solarGlowColor = new THREE.Color(0x002266).multiplyScalar(powerGlowIntensity);

  // Position coordinates for the 4 engine bells at z = 3
  const enginePositions = [
    [-0.8, 1.2, 3],
    [0.8, 1.2, 3],
    [-0.8, -1.2, 3],
    [0.8, -1.2, 3],
  ];

  // Helper arrays for rendering repeating elements
  const goldRingOffsets = [-2.2, -1.1, 0, 1.1, 2.2];
  const trussSegments = [-3.0, -2.0, -1.0, 0, 1.0, 2.0, 3.0];
  const strutOffsets = [-2.0, 0.0, 2.0];
  
  const panelLineOffsets = [];
  for (let zVal = -2.8; zVal <= 2.8; zVal += 0.35) {
    panelLineOffsets.push(zVal);
  }

  const cellWidths = [];
  for (let xVal = -2.6; xVal <= 2.6; xVal += 0.45) {
    cellWidths.push(xVal);
  }
  const cellHeights = [];
  for (let zVal = -1.6; zVal <= 1.6; zVal += 0.4) {
    cellHeights.push(zVal);
  }

  // Calculate dynamic positions of leaking fuel bubbles to render drifting gas jets
  const timeSec = typeof Date !== "undefined" ? Date.now() / 1000 : 0;
  const gasLeakOffset1 = (timeSec * 2.2) % 3.0;
  const gasLeakOffset2 = ((timeSec + 0.5) * 2.2) % 3.0;

  return (
    <group ref={groupRef}>
      
      {/* 1. SOLAR STORM PLASMA BOUNDARY OVERLAY */}
      {isSolarStorm && (
        <mesh ref={stormRef}>
          <sphereGeometry args={[4.2, 24, 24]} />
          <meshBasicMaterial 
            color="#f97316" 
            wireframe 
            transparent 
            opacity={0.15 + Math.sin(timeSec * 4) * 0.05} 
          />
        </mesh>
      )}

      {/* 2. TWIN MASSIVE FUEL CYLINDERS */}
      {/* Top Cylinder */}
      <mesh position={[0, 1.2, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.45, 0.45, 6, 32]} />
        <meshPhysicalMaterial 
          color="#e5e7eb" 
          roughness={0.65} 
          metalness={0.25}
          clearcoat={0.15}
          clearcoatRoughness={0.2}
          reflectivity={0.8}
          emissive={alertEmissive}
          emissiveIntensity={alertIntensity}
        />
        {/* Dynamic HUD label above top cylinder */}
        <Html distanceFactor={8} position={[0, 0.8, 0]}>
          <div className="bg-slate-950/90 text-cyan-400 border border-cyan-500/30 text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap font-mono select-none pointer-events-none shadow-md">
            FUEL RES: {Math.round(fuel)}%
          </div>
        </Html>
      </mesh>

      {/* Bottom Cylinder */}
      <mesh position={[0, -1.2, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.45, 0.45, 6, 32]} />
        <meshPhysicalMaterial 
          color="#e5e7eb" 
          roughness={0.65} 
          metalness={0.25}
          clearcoat={0.15}
          clearcoatRoughness={0.2}
          reflectivity={0.8}
          emissive={alertEmissive}
          emissiveIntensity={alertIntensity}
        />
      </mesh>

      {/* 3. FUEL LEAK DRIFTING GAS PLUMES */}
      {isFuelLeak && (
        <group>
          {/* Venting jet from top left tank valve */}
          <mesh position={[-0.5, 1.4, -1.5 + gasLeakOffset1]}>
            <sphereGeometry args={[0.07, 8, 8]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.65 * (1.0 - gasLeakOffset1 / 3.0)} />
          </mesh>
          <mesh position={[-0.55, 1.45, -1.5 + gasLeakOffset2]}>
            <sphereGeometry args={[0.05, 8, 8]} />
            <meshBasicMaterial color="#06b6d4" transparent opacity={0.65 * (1.0 - gasLeakOffset2 / 3.0)} />
          </mesh>
          
          {/* Venting jet from bottom right tank valve */}
          <mesh position={[0.5, -1.4, 1.0 + gasLeakOffset1]}>
            <sphereGeometry args={[0.07, 8, 8]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.65 * (1.0 - gasLeakOffset1 / 3.0)} />
          </mesh>
        </group>
      )}

      {/* 4. REINFORCEMENT GOLD FOIL BANDS */}
      {goldRingOffsets.map((zOffset, index) => (
        <React.Fragment key={`gold-rings-${index}`}>
          <mesh position={[0, 1.2, zOffset]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <torusGeometry args={[0.47, 0.04, 16, 32]} />
            <meshPhysicalMaterial 
              color="#d4af37" 
              metalness={1.0} 
              roughness={0.15}
              clearcoat={0.4}
            />
          </mesh>
          <mesh position={[0, -1.2, zOffset]} rotation={[Math.PI / 2, 0, 0]} castShadow>
            <torusGeometry args={[0.47, 0.04, 16, 32]} />
            <meshPhysicalMaterial 
              color="#d4af37" 
              metalness={1.0} 
              roughness={0.15}
              clearcoat={0.4}
            />
          </mesh>
        </React.Fragment>
      ))}

      {/* 5. SURFACE PANEL LINES */}
      {panelLineOffsets.map((zVal, index) => (
        <React.Fragment key={`panels-${index}`}>
          <mesh position={[0, 1.2, zVal]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.454, 0.005, 8, 32]} />
            <meshStandardMaterial color="#374151" roughness={0.7} />
          </mesh>
          <mesh position={[0, -1.2, zVal]} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[0.454, 0.005, 8, 32]} />
            <meshStandardMaterial color="#374151" roughness={0.7} />
          </mesh>
        </React.Fragment>
      ))}

      {/* 6. MICROMETEORITE IMPACT SPARK FLASHES */}
      {isMeteorImpact && (
        <group>
          <mesh position={[0.2, 1.3, -0.8]}>
            <sphereGeometry args={[0.1 + Math.sin(timeSec * 25) * 0.05, 8, 8]} />
            <meshBasicMaterial color="#ffffff" transparent opacity={Math.floor(timeSec * 8) % 2} />
          </mesh>
          <mesh position={[-0.3, -1.3, 1.4]}>
            <sphereGeometry args={[0.08 + Math.cos(timeSec * 20) * 0.04, 8, 8]} />
            <meshBasicMaterial color="#ea580c" transparent opacity={Math.floor(timeSec * 12) % 2} />
          </mesh>
        </group>
      )}

      {/* 7. EXPOSED SILVER PIPELINES */}
      <mesh position={[0.3, 1.6, 0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.02, 0.02, 5.6, 8]} />
        <meshPhysicalMaterial color="#9ca3af" metalness={1.0} roughness={0.15} />
      </mesh>
      <mesh position={[-0.3, 1.6, -0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.02, 0.02, 5.6, 8]} />
        <meshPhysicalMaterial color="#9ca3af" metalness={1.0} roughness={0.15} />
      </mesh>
      <mesh position={[0.3, -1.6, 0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.02, 0.02, 5.6, 8]} />
        <meshPhysicalMaterial color="#9ca3af" metalness={1.0} roughness={0.15} />
      </mesh>
      <mesh position={[-0.3, -1.6, -0.1]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.02, 0.02, 5.6, 8]} />
        <meshPhysicalMaterial color="#9ca3af" metalness={1.0} roughness={0.15} />
      </mesh>

      {/* 8. LONG CENTRAL TRUSS STRUCTURE (Spine) */}
      <mesh position={[0, 0, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.35, 0.35, 7.2]} />
        <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
      </mesh>
      
      {trussSegments.map((zOffset, index) => (
        <mesh key={`truss-seg-${index}`} position={[0, 0, zOffset]} castShadow>
          <boxGeometry args={[0.62, 0.62, 0.35]} />
          <meshPhysicalMaterial color="#374151" roughness={0.35} metalness={0.95} />
        </mesh>
      ))}

      {strutOffsets.map((zOffset, index) => (
        <React.Fragment key={`struts-${index}`}>
          <mesh position={[0, 0.6, zOffset]} castShadow>
            <cylinderGeometry args={[0.07, 0.07, 1.2, 8]} />
            <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
          </mesh>
          <mesh position={[0, -0.6, zOffset]} castShadow>
            <cylinderGeometry args={[0.07, 0.07, 1.2, 8]} />
            <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
          </mesh>
        </React.Fragment>
      ))}

      {/* 9. DOCKING MODULES & HEAT RADIATORS */}
      <mesh position={[0, 0, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.1, 0.7, 1.4]} />
        <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
      </mesh>
      <mesh position={[0, 0, -0.2]} castShadow>
        <sphereGeometry args={[0.55, 16, 16]} />
        <meshPhysicalMaterial color="#4b5563" roughness={0.3} metalness={0.9} />
      </mesh>
      <mesh position={[0, 0, -0.75]} rotation={[0, 0, 0]} castShadow>
        <torusGeometry args={[0.3, 0.06, 12, 24]} />
        <meshPhysicalMaterial color="#94a3b8" roughness={0.15} metalness={0.95} />
      </mesh>
      <mesh position={[0, 0, -2.1]} castShadow receiveShadow>
        <boxGeometry args={[2.5, 0.03, 1.1]} />
        <meshStandardMaterial color="#111827" roughness={0.85} metalness={0.1} />
      </mesh>

      {/* 10. HUGE SOLAR ARRAY WING */}
      <group ref={solarPanelRef} position={[-3.8, 0, 0]}>
        <mesh castShadow receiveShadow>
          <boxGeometry args={[5.6, 0.04, 3.6]} />
          <meshPhysicalMaterial 
            color="#0b1220" 
            emissive={solarGlowColor}
            emissiveIntensity={0.25}
            roughness={0.05} 
            metalness={0.9}
            clearcoat={1.0}
            clearcoatRoughness={0.05}
          />
          <Html distanceFactor={8} position={[-1.0, 0.3, 0]}>
            <div className="bg-slate-950/90 text-emerald-400 border border-emerald-500/30 text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap font-mono select-none pointer-events-none shadow-md">
              PV_CELL_GEN: {Math.round(power)}%
            </div>
          </Html>
        </mesh>

        {cellWidths.map((xVal, wIdx) => (
          <mesh key={`grid-w-${wIdx}`} position={[xVal, 0.024, 0]}>
            <boxGeometry args={[0.012, 0.005, 3.56]} />
            <meshBasicMaterial color="#000000" />
          </mesh>
        ))}
        {cellHeights.map((zVal, hIdx) => (
          <mesh key={`grid-h-${hIdx}`} position={[0, 0.024, zVal]}>
            <boxGeometry args={[5.56, 0.005, 0.012]} />
            <meshBasicMaterial color="#000000" />
          </mesh>
        ))}

        <mesh position={[2.8 + 0.6, 0, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
          <cylinderGeometry args={[0.08, 0.08, 1.2, 8]} />
          <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
        </mesh>
      </group>

      {/* 11. FOUR CORNER ENGINE CLUSTERS WITH PROPULSION FLICKERING */}
      {enginePositions.map((pos, index) => {
        // Thruster failure dims or disables specific nozzles
        const isThisEngineFailed = isThrusterFail && (index % 2 === 0);
        const engineBellColor = isThisEngineFailed ? "#334155" : "#555555";
        const flameMultiplier = isThisEngineFailed ? 0.0 : (isThrusterFail ? 0.35 : 1.0);
        
        return (
          <group key={`engine-${index}`} position={pos as [number, number, number]}>
            <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
              <cylinderGeometry args={[0.26, 0.13, 0.55, 32, 1, true]} />
              <meshPhysicalMaterial 
                color={engineBellColor} 
                roughness={0.3} 
                metalness={1.0} 
                side={THREE.DoubleSide} 
              />
            </mesh>
            <mesh position={[0, 0, 0.27]} rotation={[Math.PI / 2, 0, 0]} castShadow>
              <torusGeometry args={[0.25, 0.02, 8, 32]} />
              <meshPhysicalMaterial color="#2a2a2a" roughness={0.4} metalness={1.0} />
            </mesh>
            <mesh position={[0, 0, -0.27]} castShadow>
              <sphereGeometry args={[0.15, 16, 16]} />
              <meshPhysicalMaterial color="#8a8a8a" roughness={0.25} metalness={1.0} />
            </mesh>

            {/* Layered Ion Plasma exhaust flame */}
            {isEngineFiring && flameMultiplier > 0 && (
              <group>
                {/* Core (White) */}
                <mesh position={[0, 0, 0.6]} rotation={[Math.PI / 2, 0, 0]}>
                  <cylinderGeometry args={[0.07 * flameMultiplier, 0.12 * flameMultiplier, 1.2, 16]} />
                  <meshBasicMaterial color="#ffffff" transparent opacity={0.85} />
                </mesh>
                {/* Middle (Cyan) */}
                <mesh position={[0, 0, 1.0]} rotation={[Math.PI / 2, 0, 0]}>
                  <cylinderGeometry args={[0.13 * flameMultiplier, 0.23 * flameMultiplier, 2.0, 16]} />
                  <meshBasicMaterial 
                    color={isThrusterFail ? "#ea580c" : "#00e5ff"} // orange flash if failed
                    transparent 
                    opacity={0.55 * (0.85 + Math.sin(timeSec * 35) * 0.15)} // flickering animation
                  />
                </mesh>
                {/* Outer (Blue) */}
                <mesh position={[0, 0, 1.4]} rotation={[Math.PI / 2, 0, 0]}>
                  <cylinderGeometry args={[0.19 * flameMultiplier, 0.32 * flameMultiplier, 2.8, 16]} />
                  <meshBasicMaterial color="#1d4ed8" transparent opacity={0.2} />
                </mesh>
              </group>
            )}
          </group>
        );
      })}

      {/* 12. COMMUNICATION DISH (Bow antenna signal disruptions) */}
      <group ref={dishRef} position={[0, 0, -3.7]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.05, 0.05, 0.5, 8]} />
          <meshPhysicalMaterial color="#4b5563" roughness={0.4} metalness={0.9} />
        </mesh>
        <mesh position={[0, 0, -0.25]} rotation={[Math.PI / 2, 0, 0]} castShadow>
          <coneGeometry args={[0.42, 0.15, 16, 1, true]} />
          <meshPhysicalMaterial color="#4b5563" roughness={0.3} metalness={0.9} side={THREE.DoubleSide} />
        </mesh>
        
        {/* Signal emitter sphere - Cyan if connected, flashing red if comm loss occurs */}
        {telemetry?.communication === "Connected" && !isCommLoss ? (
          <mesh position={[0, 0, -0.4]}>
            <sphereGeometry args={[0.05, 8, 8]} />
            <meshBasicMaterial color="#00e5ff" />
          </mesh>
        ) : (
          <mesh position={[0, 0, -0.4]}>
            <sphereGeometry args={[0.06, 8, 8]} />
            <meshBasicMaterial color="#ef4444" transparent opacity={Math.floor(timeSec * 6) % 2} />
          </mesh>
        )}
      </group>

      {/* 13. HULL DIAGNOSTICS SHELL WRAP */}
      <group>
        <mesh position={[0, 1.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.47, 0.47, 6.02, 16]} />
          <meshBasicMaterial 
            color={healthColor} 
            wireframe 
            transparent 
            opacity={0.07 + (1 - health / 100) * 0.35} 
          />
          <Html distanceFactor={8} position={[0, -0.8, 0]}>
            <div className="bg-slate-950/90 text-slate-100 border border-slate-700/30 text-[9px] px-1.5 py-0.5 rounded whitespace-nowrap font-mono select-none pointer-events-none shadow-md">
              HULL DIAGNOSTICS: <span style={{ color: healthColor }} className="font-bold">{Math.round(health)}%</span>
            </div>
          </Html>
        </mesh>
        <mesh position={[0, -1.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.47, 0.47, 6.02, 16]} />
          <meshBasicMaterial 
            color={healthColor} 
            wireframe 
            transparent 
            opacity={0.07 + (1 - health / 100) * 0.35} 
          />
        </mesh>
      </group>

      {/* 14. NAV LIGHTS */}
      <mesh ref={lightGreenRef} position={[0.7, 1.6, -2.8]}>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshBasicMaterial color="#00ff88" transparent opacity={0.8} />
      </mesh>
      <mesh ref={lightRedRef} position={[-0.7, 1.6, -2.8]}>
        <sphereGeometry args={[0.06, 8, 8]} />
        <meshBasicMaterial color="#ff4444" transparent opacity={0.8} />
      </mesh>

    </group>
  );
}

interface Spacecraft3DProps {
  telemetry: Telemetry | null;
  state: string;
  activeEvents: ActiveEvent[];
}

export default function Spacecraft3D({ telemetry, state, activeEvents }: Spacecraft3DProps) {
  return (
    <div className="w-full h-full relative min-h-[350px] md:min-h-[420px]">
      <div className="absolute top-4 left-4 z-10 font-mono text-[9px] text-cyan-400/80 bg-slate-950/80 px-2 py-1.5 rounded border border-cyan-500/20 backdrop-blur-sm pointer-events-none select-none shadow-md">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" />
          <span>PHM_STATE_ENGINE: ACTIVE</span>
        </div>
        <p>SPATIAL_ORBIT: Z_PLANE_AXIS</p>
        <p>SYSTEM_RECORDS: 1Hz_TICK</p>
      </div>

      <Canvas camera={{ position: [8, 2, 8], fov: 32 }}>
        <color attach="background" args={["#000814"]} />
        
        <ambientLight intensity={0.2} />
        
        <directionalLight 
          position={[15, 10, 5]} 
          intensity={2.5} 
          castShadow 
          shadow-mapSize-width={1024} 
          shadow-mapSize-height={1024} 
        />
        
        <directionalLight 
          position={[-15, 5, -5]} 
          intensity={1.0} 
          color="#38bdf8" 
        />
        
        <directionalLight 
          position={[0, -2, -15]} 
          intensity={2.0} 
          color="#00e5ff" 
        />

        <pointLight 
          position={[0, -8, 0]} 
          intensity={1.2} 
          color="#1d4ed8" 
        />

        <React.Suspense fallback={null}>
          <SpacecraftModel telemetry={telemetry} state={state} activeEvents={activeEvents} />
        </React.Suspense>

        <Stars radius={110} depth={50} count={3500} factor={6} saturation={0.4} fade speed={1.0} />

        <OrbitControls enableZoom={true} enablePan={true} maxDistance={15} minDistance={4.0} />
      </Canvas>
    </div>
  );
}
