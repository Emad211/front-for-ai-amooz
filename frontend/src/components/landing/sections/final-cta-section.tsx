'use client';

import { Button } from '@/components/ui/button';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useLanding } from '@/hooks/use-landing';

export const FinalCTASection = () => {
    const { cta } = useLanding();

    return (
        <section className="py-20 md:py-32 relative bg-primary/10 dark:bg-primary/5">
            <div className="container mx-auto px-4 relative z-10">
                <div className="max-w-3xl mx-auto text-center">
                    <h2 className="text-2xl md:text-5xl font-bold text-foreground mb-4 md:mb-6">
                        {cta.title}
                    </h2>
                    <p className="text-base md:text-lg text-muted-foreground mb-8 md:mb-10 max-w-xl mx-auto px-4">
                        {cta.description}
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 px-6 sm:px-0">
                        <Button asChild size="lg" className="w-full sm:w-auto h-12 md:h-14 px-10 text-base md:text-lg bg-primary text-primary-foreground hover:bg-primary/90 shadow-xl shadow-primary/25 transition-all hover:scale-105">
                            <Link href="/login">
                                {cta.button}
                                <ArrowLeft className="mr-2 h-5 w-5" />
                            </Link>
                        </Button>
                    </div>
                    <p className="text-xs md:text-sm text-muted-foreground mt-6">
                        {cta.footer}
                    </p>
                </div>
            </div>
        </section>
    );
};
