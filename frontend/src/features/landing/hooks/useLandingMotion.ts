import gsap from 'gsap'
import { useGSAP } from '@gsap/react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import type { RefObject } from 'react'

gsap.registerPlugin(useGSAP, ScrollTrigger)

export function useLandingMotion(containerRef: RefObject<HTMLElement | null>) {
  useGSAP(
    () => {
      const media = gsap.matchMedia()

      media.add(
        {
          reduceMotion: '(prefers-reduced-motion: reduce)',
          allowMotion: '(prefers-reduced-motion: no-preference)',
        },
        (context) => {
          const reduceMotion = Boolean(context.conditions?.reduceMotion)

          if (reduceMotion) {
            gsap.set('[data-reveal]', { autoAlpha: 1, y: 0 })
            return
          }

          const heroItems = gsap.utils.toArray<HTMLElement>('[data-reveal="hero"]')
          gsap.from(heroItems, {
            autoAlpha: 0,
            y: 18,
            duration: 0.7,
            stagger: 0.08,
            ease: 'power2.out',
          })

          gsap.utils.toArray<HTMLElement>('[data-reveal="section"]').forEach((section) => {
            gsap.from(section, {
              autoAlpha: 0,
              y: 20,
              duration: 0.7,
              ease: 'power2.out',
              scrollTrigger: {
                trigger: section,
                start: 'top 88%',
                once: true,
              },
            })
          })

          gsap.utils.toArray<HTMLElement>('[data-reveal="module"]').forEach((module) => {
            gsap.from(module, {
              autoAlpha: 0,
              y: 16,
              duration: 0.6,
              ease: 'power2.out',
              scrollTrigger: {
                trigger: module,
                start: 'top 90%',
                once: true,
              },
            })
          })

          gsap.to('[data-preview]', {
            y: -20,
            ease: 'none',
            scrollTrigger: {
              trigger: '[data-preview]',
              start: 'top 85%',
              end: 'bottom top',
              scrub: 0.8,
            },
          })

          const polylines = gsap.utils.toArray<SVGPolylineElement>('polyline')
          polylines.forEach((line) => {
            const length = line.getTotalLength()
            if (!length) return
            gsap.fromTo(
              line,
              { strokeDasharray: length, strokeDashoffset: length },
              {
                strokeDashoffset: 0,
                duration: 1.4,
                ease: 'power2.out',
                delay: 0.35,
              },
            )
          })
        },
      )

      return () => {
        media.revert()
      }
    },
    { scope: containerRef },
  )
}
