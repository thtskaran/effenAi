"use client";

import { useEffect, useRef, useState } from "react";
import Script from "next/script";

interface TurnstileProps {
  siteKey: string;
  onVerify: (token: string) => void;
}

interface TurnstileInstance {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "refresh-expired": string;
      [key: string]: any;
    }
  ) => string;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileInstance;
  }
}

export function Turnstile({ siteKey, onVerify }: TurnstileProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const [scriptLoaded, setScriptLoaded] = useState(false);
  const hasRendered = useRef(false);
  const onVerifyRef = useRef(onVerify);

  // Update onVerifyRef when onVerify changes
  useEffect(() => {
    onVerifyRef.current = onVerify;
  }, [onVerify]);

  // Handle script loading separately
  useEffect(() => {
    if (window.turnstile) {
      setScriptLoaded(true);
    }

    const handleTurnstileLoad = () => {
      setScriptLoaded(true);
    };

    document.addEventListener("turnstile-loaded", handleTurnstileLoad);

    return () => {
      document.removeEventListener("turnstile-loaded", handleTurnstileLoad);
    };
  }, []);

  // Handle widget rendering separately
  useEffect(() => {
    if (!scriptLoaded || !containerRef.current || hasRendered.current) return;

    const renderWidget = () => {
      try {
        // Only render if we haven't already
        if (!widgetId.current && window.turnstile) {
          widgetId.current = window.turnstile.render(containerRef.current!, {
            sitekey: siteKey,
            callback: (token: string) => {
              onVerifyRef.current(token);
            },
            "refresh-expired": "auto",
          });
          hasRendered.current = true;
        }
      } catch (error) {
        console.error("Error rendering Turnstile widget:", error);
      }
    };

    renderWidget();

    return () => {
      try {
        if (widgetId.current && window.turnstile) {
          window.turnstile.remove(widgetId.current);
          widgetId.current = null;
          hasRendered.current = false;
        }
      } catch (error) {
        console.error("Error cleaning up Turnstile widget:", error);
      }
    };
  }, [scriptLoaded, siteKey]); // Remove onVerify from dependencies

  return (
    <div>
      <div ref={containerRef} className="my-3" />
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        async
        defer
        onLoad={() => {
          document.dispatchEvent(new Event("turnstile-loaded"));
        }}
      />
    </div>
  );
}
