export function contentRelevance(item, regionName = "") {
  const alias = regionName.replace(/[시군구]$/, "");
  const tags = Array.isArray(item.tags) ? item.tags.filter((tag) => typeof tag === "string") : [];
  const matches = (text) => alias.length >= 2 && typeof text === "string" && text.includes(alias);
  const matchedFields = [
    matches(item.title) && "제목",
    matches(item.description) && "설명",
    tags.some(matches) && "태그",
  ].filter(Boolean);
  const excluded = item.content_type === "관광무관";
  const uncertain = !Number.isFinite(item.confidence) || item.confidence < 0.6;
  const confirmed = matchedFields.length > 0 && !excluded && !uncertain;
  return { tags, matchedFields, confirmed, label: excluded ? "관광 관련성 낮음" : uncertain ? "분류 확인 필요" : confirmed ? `${matchedFields.join("·")}에 ${alias} 언급` : "지역 관련성 확인 필요" };
}
