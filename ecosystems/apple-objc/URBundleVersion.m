#import <Foundation/Foundation.h>

@interface URBundleVersion : NSObject
+ (NSComparisonResult)compareVersion:(NSString *)lhs to:(NSString *)rhs;
@end

@implementation URBundleVersion

+ (NSArray<NSNumber *> *)components:(NSString *)value {
    NSMutableArray<NSNumber *> *parts = [NSMutableArray array];
    for (NSString *piece in [value componentsSeparatedByString:@"."]) {
        NSScanner *scanner = [NSScanner scannerWithString:piece];
        NSInteger number = 0;
        if (![scanner scanInteger:&number]) {
            number = 0;
        }
        [parts addObject:@(number)];
    }
    return parts;
}

+ (NSComparisonResult)compareVersion:(NSString *)lhs to:(NSString *)rhs {
    NSArray<NSNumber *> *a = [self components:lhs];
    NSArray<NSNumber *> *b = [self components:rhs];
    NSUInteger count = MAX(a.count, b.count);

    for (NSUInteger i = 0; i < count; i++) {
        NSInteger av = i < a.count ? a[i].integerValue : 0;
        NSInteger bv = i < b.count ? b[i].integerValue : 0;
        if (av < bv) return NSOrderedAscending;
        if (av > bv) return NSOrderedDescending;
    }
    return NSOrderedSame;
}

@end
