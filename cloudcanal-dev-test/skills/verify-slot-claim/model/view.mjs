export const title = "Slot claim";

export const state = (v) => {
  if (v.owner === 0 && v.live === 0) return "Slot free";
  if (v.owner !== 0 && v.owner === v.live) return "Slot held";
  return "Stale release cleared the holder";
};

export const step = (_action, from, to) => {
  const before = state(from);
  const after = state(to);
  if (before === after) return null;
  if (before === "Slot free" && after === "Slot held") return "a caller reserves the slot";
  if (before === "Slot held" && after === "Slot free") return "the holder releases its own claim";
  if (after === "Stale release cleared the holder") return "a caller releases with an older claim id";
  return null;
};
