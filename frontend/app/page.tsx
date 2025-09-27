import { title, subtitle } from "@/components/primitives";

export default function Home() {
  return (
    <section className="flex flex-col items-center justify-center gap-4 py-8 md:py-10">
      <div className="inline-block max-w-xl text-center justify-center">
        <span className={title()}>Welcome to&nbsp;</span>
        <span className={title({ color: "violet" })}>Translator App</span>
        <div className={subtitle({ class: "mt-4" })}>
          A modern translation application built with Next.js and HeroUI.
        </div>
      </div>
    </section>
  );
}
