"use client";

const URL_RE = /((?:https?:\/\/|www\.)[^\s<>"']+)/gi;

function hrefFor(value: string) {
  return value.toLowerCase().startsWith("www.") ? `https://${value}` : value;
}

export function LinkedText({ text }: { text: string }) {
  const parts = text.split(URL_RE);
  return (
    <>
      {parts.map((part, index) => {
        if (part.match(URL_RE)) {
          return (
            <a
              className="linked-text"
              href={hrefFor(part)}
              key={`${part}-${index}`}
              onClick={(event) => event.stopPropagation()}
              rel="noopener noreferrer"
              target="_blank"
            >
              {part}
            </a>
          );
        }
        return <span key={`${part}-${index}`}>{part}</span>;
      })}
    </>
  );
}
