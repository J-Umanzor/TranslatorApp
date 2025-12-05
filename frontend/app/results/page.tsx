"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Accordion, AccordionItem } from "@heroui/accordion";
import { title } from "@/components/primitives";

type Metadata = {
  pages: number;
  kind: string;
  source_language: string;
  target_language: string;
};

export default function ResultsPage() {
  const router = useRouter();
  const [translatedPdfDataUrl, setTranslatedPdfDataUrl] = useState<string | null>(null);
  const [originalText, setOriginalText] = useState<string>("");
  const [translatedText, setTranslatedText] = useState<string>("");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Retrieve data from sessionStorage and IndexedDB
    const loadData = () => {
      const storedOriginalText = sessionStorage.getItem("originalText");
      const storedTranslatedText = sessionStorage.getItem("translatedText");
      const storedMetadata = sessionStorage.getItem("metadata");

      // Load text and metadata from sessionStorage
      if (storedOriginalText) {
        setOriginalText(storedOriginalText);
      }

      if (storedTranslatedText) {
        setTranslatedText(storedTranslatedText);
      }

      if (storedMetadata) {
        try {
          setMetadata(JSON.parse(storedMetadata));
        } catch (e) {
          console.error("Failed to parse metadata", e);
        }
      }

      // Check if we have any data at all
      if (!storedOriginalText && !storedTranslatedText) {
        // Try IndexedDB before showing error
        const dbRequest = indexedDB.open("TranslationDB", 1);
        dbRequest.onsuccess = () => {
          const db = dbRequest.result;
          if (!db.objectStoreNames.contains("pdfs")) {
            setError("No translation data found. Please translate a document first.");
            setIsLoading(false);
            return;
          }
        };
        dbRequest.onerror = () => {
          setError("No translation data found. Please translate a document first.");
          setIsLoading(false);
        };
      }

      // Load translated PDF from IndexedDB
      const dbRequest = indexedDB.open("TranslationDB", 1);
      
      dbRequest.onerror = () => {
        setIsLoading(false);
        setError("Failed to load translated PDF from storage.");
      };
      
      dbRequest.onsuccess = () => {
        const db = dbRequest.result;
        
        // Check if object store exists
        if (!db.objectStoreNames.contains("pdfs")) {
          setIsLoading(false);
          setError("No translation data found. Please translate a document first.");
          return;
        }
        
        const transaction = db.transaction(["pdfs"], "readonly");
        const store = transaction.objectStore("pdfs");
        
        // Load translated PDF
        const translatedRequest = store.get("translatedPdf");
        translatedRequest.onsuccess = () => {
          if (translatedRequest.result && translatedRequest.result.base64) {
            try {
              const base64Data = translatedRequest.result.base64;
              
              if (!base64Data || base64Data.length === 0) {
                console.error("Translated PDF base64 data is empty");
                setError("Translated PDF data is invalid.");
                setIsLoading(false);
                return;
              }
              
              // Convert base64 to blob and create blob URL (more reliable than data URLs in iframes)
              const byteCharacters = atob(base64Data);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i += 1) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: "application/pdf" });
              
              if (blob.size > 0) {
                const blobUrl = URL.createObjectURL(blob);
                setTranslatedPdfDataUrl(blobUrl);
                console.log("Translated PDF loaded from IndexedDB, blob size:", blob.size, "bytes");
                setIsLoading(false);
              } else {
                console.error("Translated PDF blob is empty");
                setError("Translated PDF data is invalid.");
                setIsLoading(false);
              }
            } catch (error) {
              console.error("Failed to create blob URL for translated PDF:", error);
              setError("Failed to load translated PDF.");
              setIsLoading(false);
            }
          } else {
            console.warn("Translated PDF not found in IndexedDB");
            setError("Translated PDF not found. Please translate a document first.");
            setIsLoading(false);
          }
        };
        
        translatedRequest.onerror = (event) => {
          console.error("IndexedDB error loading translated PDF:", event);
          setError("Failed to load translated PDF from storage.");
          setIsLoading(false);
        };
      };
      
      dbRequest.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains("pdfs")) {
          db.createObjectStore("pdfs", { keyPath: "id" });
        }
      };
    };
    
    loadData();
  }, []);

  const formatLanguage = (code: string | null) => {
    if (!code || code === "unknown") {
      return "Unknown";
    }
    try {
      if (typeof Intl !== "undefined" && typeof Intl.DisplayNames === "function") {
        const formatter = new Intl.DisplayNames(["en"], { type: "language" });
        return formatter.of(code) ?? code.toUpperCase();
      }
    } catch {
      // ignore formatter errors
    }
    return code.toUpperCase();
  };

  const handleDownloadTranslatedPdf = () => {
    if (!translatedPdfDataUrl) {
      return;
    }

    try {
      // If it's a blob URL, use it directly
      if (translatedPdfDataUrl.startsWith("blob:")) {
        const link = document.createElement("a");
        link.href = translatedPdfDataUrl;
        link.download = `translated_document_${metadata?.target_language || "translated"}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else if (translatedPdfDataUrl.startsWith("data:")) {
        // For data URLs, create a temporary blob URL for download
        const base64Match = translatedPdfDataUrl.match(/base64,(.+)$/);
        if (!base64Match) {
          setError("Failed to extract PDF data for download.");
          return;
        }
        
        const base64 = base64Match[1];
        const byteCharacters = atob(base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i += 1) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        const baseName = "translated_document";
        link.href = url;
        link.download = `${baseName}_${metadata?.target_language || "translated"}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Failed to prepare translated PDF", error);
      setError("Failed to prepare translated PDF for download.");
    }
  };

  const handleTranslateAnother = () => {
    // Revoke blob URL if it exists
    if (translatedPdfDataUrl && translatedPdfDataUrl.startsWith("blob:")) {
      URL.revokeObjectURL(translatedPdfDataUrl);
    }
    
    // Clean up session storage and IndexedDB
    sessionStorage.removeItem("originalText");
    sessionStorage.removeItem("translatedText");
    sessionStorage.removeItem("metadata");
    
    // Clean up IndexedDB
    const dbRequest = indexedDB.open("TranslationDB", 1);
    dbRequest.onsuccess = () => {
      const db = dbRequest.result;
      if (db.objectStoreNames.contains("pdfs")) {
        const transaction = db.transaction(["pdfs"], "readwrite");
        const store = transaction.objectStore("pdfs");
        store.delete("translatedPdf");
      }
    };
    
    router.push("/");
  };

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (translatedPdfDataUrl && translatedPdfDataUrl.startsWith("blob:")) {
        URL.revokeObjectURL(translatedPdfDataUrl);
      }
    };
  }, [translatedPdfDataUrl]);

  if (isLoading) {
    return (
      <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
        <div className="text-center">
          <p className="text-lg">Loading translation results...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
        <Card className="w-full max-w-2xl">
          <CardBody className="p-8 text-center">
            <p className="text-danger-500 mb-4">{error}</p>
            <Button color="primary" onPress={handleTranslateAnother}>
              Translate Another Document
            </Button>
          </CardBody>
        </Card>
      </section>
    );
  }

  return (
    <section className="flex flex-col items-center gap-8 py-8 md:py-10 w-full">
      {/* Header */}
      <div className="inline-block max-w-2xl text-center justify-center">
        <span className={title()}>Translation&nbsp;</span>
        <span className={title({ color: "violet" })}>Results</span>
      </div>

      {/* Metadata Card */}
      {metadata && (
        <Card className="w-full max-w-[98vw]">
          <CardBody className="p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="space-y-2">
                <p className="font-semibold text-lg">
                  {formatLanguage(metadata.source_language)} → {formatLanguage(metadata.target_language)}
                </p>
                <p className="text-sm text-default-500">
                  {metadata.pages} page{metadata.pages === 1 ? "" : "s"} ·{" "}
                  {metadata.kind === "scanned" ? "Scanned PDF" : "Digital PDF"}
                </p>
              </div>
              <div className="flex gap-2">
                {translatedPdfDataUrl && (
                  <Button color="secondary" onPress={handleDownloadTranslatedPdf}>
                    Download Translated PDF
                  </Button>
                )}
                <Button color="primary" variant="bordered" onPress={handleTranslateAnother}>
                  Translate Another
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* PDF Viewer */}
      <div className="w-full max-w-[98vw]">
        <Card className="w-full">
          <CardBody className="p-1">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold">Translated PDF</h3>
            </div>
            <div className="border border-default-200 rounded-lg overflow-hidden shadow-lg relative">
              {translatedPdfDataUrl ? (
                <iframe
                  key={translatedPdfDataUrl}
                  src={translatedPdfDataUrl}
                  className="w-full"
                  style={{ minHeight: "850px", height: "95vh" }}
                  title="Translated PDF"
                  onLoad={() => console.log("Translated PDF iframe loaded successfully")}
                  onError={(e) => {
                    console.error("Translated PDF iframe error:", e);
                    setError("Failed to load translated PDF. The file may be corrupted or too large.");
                  }}
                />
              ) : (
                <div className="border border-default-200 rounded-lg p-8 text-center flex items-center justify-center" style={{ minHeight: "850px", height: "95vh" }}>
                  <p className="text-default-500">Translated PDF is being loaded...</p>
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Text Preview Accordion */}
      {(originalText || translatedText) && (
        <Card className="w-full max-w-[98vw]">
          <CardBody className="p-6">
            <Accordion>
              {originalText ? (
                <AccordionItem
                  key="original-text"
                  aria-label="Original Text"
                  title="Original Text Preview"
                >
                  <p className="text-sm text-default-500 whitespace-pre-wrap max-h-96 overflow-y-auto border border-default-200 rounded-md p-4 bg-default-50">
                    {originalText.slice(0, 5000)}
                    {originalText.length > 5000 ? "..." : ""}
                  </p>
                </AccordionItem>
              ) : null}
              {translatedText ? (
                <AccordionItem
                  key="translated-text"
                  aria-label="Translated Text"
                  title="Translated Text Preview"
                >
                  <p className="text-sm text-default-500 whitespace-pre-wrap max-h-96 overflow-y-auto border border-default-200 rounded-md p-4 bg-default-50">
                    {translatedText.slice(0, 5000)}
                    {translatedText.length > 5000 ? "..." : ""}
                  </p>
                </AccordionItem>
              ) : null}
            </Accordion>
          </CardBody>
        </Card>
      )}
    </section>
  );
}

