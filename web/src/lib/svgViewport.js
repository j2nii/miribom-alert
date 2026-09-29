// SVG의 기본 preserveAspectRatio("xMidYMid meet")가 실제로 하는 스케일 계산.
// width:100%인 SVG를 max-height로도 누르면(예: forecast-plot), 박스 비율과
// viewBox 비율이 달라져 그려지는 내용이 박스보다 작아지고 가운데로 몰린다
// (letterbox/pillarbox). 박스 크기만 보고 좌표를 계산하면 이 여백만큼 어긋난다.
export function svgFit(boxWidth, boxHeight, viewWidth, viewHeight) {
  const scale = Math.min(boxWidth / viewWidth, boxHeight / viewHeight);
  return {
    scale,
    offsetX: (boxWidth - viewWidth * scale) / 2,
    offsetY: (boxHeight - viewHeight * scale) / 2,
  };
}
