import { useEffect, useRef, useState } from "react";
import { GLOSSARY } from "../../lib/glossary.js";

// 내부 용어에 점선 밑줄을 달고, 누르면 뜻을 그 자리에서 펼친다.
//
// 브라우저 기본 title 속성만으로는 부족하다 -- 모바일에서는 아예 뜨지 않고, 호버로만 보이는
// 설명은 "여기 설명이 있다"는 사실 자체가 보이지 않는다. 점선 밑줄은 눌러 볼 것이 있다는
// 표시이고, 클릭은 터치에서도 똑같이 동작한다.
export default function Term({ name, children }) {
  const entry = GLOSSARY[name];
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (!ref.current?.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // 사전에 없는 말이면 그냥 글자로 둔다 -- 장식이 목적이 아니다.
  if (!entry) return <>{children ?? name}</>;

  return (
    <span className="term-wrap" ref={ref}>
      <button
        type="button"
        className="term"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {children ?? name}
      </button>
      {open && (
        <span className="term__pop" role="note">
          <strong>{entry.term}</strong>
          {entry.desc}
        </span>
      )}
    </span>
  );
}
