.text
.globl upstreamradar_fnv1a64
.type upstreamradar_fnv1a64,@function

# uint64_t upstreamradar_fnv1a64(const unsigned char *data, size_t len)
upstreamradar_fnv1a64:
    movabs $0xcbf29ce484222325, %rax
    movabs $0x100000001b3, %r8
    xor %rcx, %rcx
.Lloop:
    cmp %rsi, %rcx
    jae .Ldone
    movzbq (%rdi,%rcx,1), %rdx
    xor %rdx, %rax
    imul %r8, %rax
    inc %rcx
    jmp .Lloop
.Ldone:
    ret

.size upstreamradar_fnv1a64, .-upstreamradar_fnv1a64
