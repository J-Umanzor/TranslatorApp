export type SiteConfig = typeof siteConfig;

export const siteConfig = {
  name: "AI PDF Translator",
  description: "Upload your PDF documents and translate them to any language using advanced AI technology.",
  navItems: [
    {
      label: "Home",
      href: "/",
    },
    {
      label: "Chat",
      href: "/chat",
    },
  ],
  navMenuItems: [],
  links: {
    github: "https://github.com/J-Umanzor/translator-app",
    docs: "/docs",
  },
};
