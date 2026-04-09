import { auth } from '@clerk/nextjs/server';
import Navbar from './components/Navbar/Navbar';
import Hero from './components/Hero/Hero';
import ProblemSolution from './components/ProblemSolution/ProblemSolution';
import HowItWorks from './components/HowItWorks/HowItWorks';
import CoursePreview from './components/CoursePreview/CoursePreview';
import FeaturesGrid from './components/FeaturesGrid/FeaturesGrid';
import Testimonials from './components/Testimonials/Testimonials';
import Marquee from './components/Marquee/Marquee';
import Stats from './components/Stats/Stats';
import FAQ from './components/FAQ/FAQ';
import CTA from './components/CTA/CTA';
import Footer from './components/Footer/Footer';
import StickyNav from './components/StickyNav/StickyNav';
import Cursor from './components/Cursor/Cursor';
import LoadingScreen from './components/LoadingScreen/LoadingScreen';
import EasterEgg from './components/EasterEgg/EasterEgg';

export default async function Home() {
  const { userId } = await auth();
  const isAuthenticated = !!userId;

  return (
    <main>
      <LoadingScreen />
      <Cursor />
      <StickyNav />
      <EasterEgg />
      <Navbar isAuthenticated={isAuthenticated} />

      <section id="hero">
        <Hero isAuthenticated={isAuthenticated} />
      </section>

      <section id="problem">
        <ProblemSolution />
      </section>

      <section id="process">
        <HowItWorks />
      </section>

      <section id="preview">
        <CoursePreview />
      </section>

      <section id="features">
        <FeaturesGrid />
      </section>

      <Marquee />

      <section id="testimonials">
        <Testimonials />
      </section>

      <section id="stats">
        <Stats />
      </section>

      <section id="faq">
        <FAQ />
      </section>

      <section id="cta">
        <CTA isAuthenticated={isAuthenticated} />
      </section>

      <Footer isAuthenticated={isAuthenticated} />
    </main>
  );
}
