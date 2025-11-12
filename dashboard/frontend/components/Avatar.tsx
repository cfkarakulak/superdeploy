import type React from "react";

interface AvatarProps {
  nameOrEmail: string;
}

const pastelColors = [
  "#3B4252", // dark blue-gray
  "#434C5E", // dark slate
  "#4C566A", // dark gray
  "#5E81AC", // soft blue
  "#81A1C1", // soft steel
  "#8FBCBB", // soft teal
  "#A3BE8C", // soft green
  "#B48EAD", // soft purple
  "#D08770", // soft orange
  "#BF616A", // soft red
];

const getInitial = (nameOrEmail: string) => {
  const trimmed = nameOrEmail.trim();
  return trimmed[0]?.toUpperCase() || "?";
};

const getPastelColor = (str: string) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  const idx = Math.abs(hash) % pastelColors.length;
  return pastelColors[idx];
};

export const Avatar: React.FC<AvatarProps> = ({ nameOrEmail }) => {
  const initial = getInitial(nameOrEmail);
  const backgroundColor = getPastelColor(nameOrEmail);

  return (
    <div
      className="flex size-5 rounded-md items-center justify-center text-[11px] text-white select-none"
      style={{ backgroundColor }}
    >
      {initial}
    </div>
  );
};

