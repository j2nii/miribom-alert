// UI examples only. Replace with consecutive collection snapshots later.
export const MORNING_BRIEFINGS = {
  yeongwol: {
    published: 18, previous: 8, average: 6, discoveredOlder: 4,
    headline: "새 영상이 평소보다 3배 많아요",
    topics: [
      { name: "촬영지 방문 후기", count: 11, previous: 3, action: "영상에 나온 장소의 안내·주차 정보 확인", videos: ["영화 속 장면을 따라간 영월 하루 여행", "촬영지 방문 전 알아둘 이동 동선"] },
      { name: "시장·먹거리 여행", count: 5, previous: 3, action: "장날·운영시간 안내의 정확성 확인", videos: ["영월 장날에 둘러본 시장 먹거리"] },
      { name: "숙박·체류 후기", count: 2, previous: 2, action: "후속 영상과 댓글 반응 관찰", videos: ["영월에서 보낸 주말 여행 기록"] },
    ],
  },
  geoje: {
    published: 4, previous: 6, average: 5, discoveredOlder: 2,
    headline: "새 영상 수는 평소 수준이에요",
    topics: [
      { name: "해안 산책·풍경", count: 2, previous: 3, action: "새로운 주제의 등장 여부 관찰", videos: ["거제 바닷길 산책 기록"] },
      { name: "맛집 방문 후기", count: 1, previous: 2, action: "지역 정보가 정확히 소개되는지 확인", videos: ["거제 여행 중 들른 식당"] },
      { name: "체험 여행", count: 1, previous: 1, action: "추가 영상 게시 추이 관찰", videos: ["주말 거제 체험 여행 후기"] },
    ],
  },
  chungju: {
    published: 12, previous: 7, average: 8, discoveredOlder: 3,
    headline: "새 영상이 평소보다 1.5배 많아요",
    topics: [
      { name: "지역 소개·반응", count: 7, previous: 3, action: "지역에 대한 주요 반응 확인", videos: ["충주가 궁금해진 이유", "영상 보고 찾아본 충주 이야기"] },
      { name: "당일 여행", count: 3, previous: 2, action: "소개된 동선과 안내 정보 확인", videos: ["충주 당일 여행 동선 정리"] },
      { name: "시장·먹거리", count: 2, previous: 2, action: "추가 언급 여부 관찰", videos: ["충주 시장 먹거리 둘러보기"] },
    ],
  },
};
