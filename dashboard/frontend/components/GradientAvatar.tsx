"use client";

interface AvatarData {
  width: string;
  height: string;
  background: string;
  shapes: Array<{
    size: string;
    background: string;
    top: string;
    left: string;
    blur: string;
  }>;
}

interface GradientAvatarProps {
  name: string;
  width?: number;
  height?: number;
  className?: string;
}

// Gradient avatar generator based on name
const generateAvatar = (name: string, width: number, height: number): AvatarData => {
  const hash = Array.from(name).reduce((acc, char) => acc + char.charCodeAt(0), 0);

  const getRandomColor = (offset = 0) => {
    const h = (hash * (13 + offset)) % 360; // Hue
    const s = 60 + ((hash * (17 + offset)) % 30); // Saturation (60-90%)
    const l = 50 + ((hash * (23 + offset)) % 20); // Lightness (50-70%)
    return `hsla(${h}, ${s}%, ${l}%, 0.9)`; // Slight transparency for blending
  };

  const shapes = Array(3)
    .fill(null)
    .map((_, i) => {
      const size = 30 + ((hash * (7 + i)) % 50);
      const top = (hash * (11 + i)) % 100;
      const left = (hash * (19 + i)) % 100;
      const blur = 5 + ((hash * (29 + i)) % 20);

      return {
        size: `${size}px`,
        background: getRandomColor(i + 3),
        top: `${top}%`,
        left: `${left}%`,
        blur: `${blur}px`,
      };
    });

  return {
    width: `${width}px`,
    height: `${height}px`,
    background: `linear-gradient(
        135deg,
        ${getRandomColor(1)},
        ${getRandomColor(2)},
        #ce2c1a,
        ${getRandomColor(3)}
      )`,
    shapes,
  };
};

// Generate a gradient avatar component
export const GradientAvatar = ({
  name,
  width = 24,
  height = 24,
  className = "",
}: GradientAvatarProps) => {
  const avatarData: AvatarData = generateAvatar(name || "user", width, height);

  return (
    <div
      className={`rounded-full relative overflow-hidden ${className}`}
      style={{
        width: avatarData.width,
        height: avatarData.height,
        background: avatarData.background,
        boxShadow: "0 4px 10px rgba(0, 0, 0, 0.1)",
      }}
    >
      {avatarData.shapes.map((shape, i) => (
        <span
          key={`shape-${i}-${shape.top}-${shape.left}`}
          style={{
            width: shape.size,
            height: shape.size,
            background: shape.background,
            position: "absolute",
            top: shape.top,
            left: shape.left,
            borderRadius: "50%",
            filter: `blur(${shape.blur})`,
          }}
        />
      ))}
    </div>
  );
};

