export function FaceTracker({ locked }: { locked: boolean }) {
  const borderColor = locked ? "#9CD3A8" : "#9CB5A4";

  return (
    <div
      className="absolute top-1/2 left-1/2 w-[214px] h-[214px] rounded-full transition-colors"
      style={{ transform: "translate(-50%, -46%)", border: `1.5px solid ${borderColor}` }}
    >
      {[
        "top-[-1px] left-[-1px] border-t-2 border-l-2",
        "top-[-1px] right-[-1px] border-t-2 border-r-2",
        "bottom-[-1px] left-[-1px] border-b-2 border-l-2",
        "bottom-[-1px] right-[-1px] border-b-2 border-r-2",
      ].map((pos, i) => (
        <span
          key={i}
          className={`absolute w-4 h-4 border-[#C9D9CD] ${pos}`}
        />
      ))}
    </div>
  );
}