"use client";

interface GradientAvatarProps {
  name: string;
  size?: number;
}

export function GradientAvatar({ name, size = 24 }: GradientAvatarProps) {
  // Simple hash function to generate consistent colors from name
  const hashCode = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash;
    }
    return Math.abs(hash);
  };

  const hash = hashCode(name);
  
  // Generate gradient colors
  const hue1 = hash % 360;
  const hue2 = (hash + 60) % 360;
  const hue3 = (hash + 120) % 360;

  return (
    <div
      className="rounded-full relative overflow-hidden"
      style={{
        width: size,
        height: size,
        background: `linear-gradient(135deg, hsl(${hue1}, 70%, 60%), hsl(${hue2}, 70%, 50%))`,
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
      }}
    >
      {/* Orb effect circles */}
      <span
        style={{
          width: size * 0.6,
          height: size * 0.6,
          background: `hsl(${hue2}, 80%, 70%)`,
          position: "absolute",
          top: "-20%",
          left: "-10%",
          borderRadius: "50%",
          filter: "blur(8px)",
          opacity: 0.7,
        }}
      />
      <span
        style={{
          width: size * 0.5,
          height: size * 0.5,
          background: `hsl(${hue3}, 80%, 65%)`,
          position: "absolute",
          bottom: "-15%",
          right: "-5%",
          borderRadius: "50%",
          filter: "blur(6px)",
          opacity: 0.6,
        }}
      />
    </div>
  );
}
