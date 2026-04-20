import Header from '@/components/Header';
import Footer from '@/components/Footer';

export default function ShellLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div id="app-root">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[9999] focus:bg-white focus:px-4 focus:py-2 focus:text-primary-600 focus:underline"
      >
        Skip to main content
      </a>
      <Header />
      <div id="main-content">
        {children}
      </div>
      <Footer />
    </div>
  );
}
