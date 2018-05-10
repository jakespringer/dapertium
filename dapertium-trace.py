import argparse
import graphviz
import re

def remove_comment_from_line(line):
    return re.split('(?<!%)\\!', line)[0]

def filter_blank_lines(line):
    return line.strip() != ''

def separate_symbols_lexicon(lines):
    sections = []
    current = []
    for line in lines:
        if line == 'Multichar_Symbols':
            if len(current) > 0:
                sections.append(current)
            current = ['Multichar_Symbols']
        elif line.startswith('LEXICON'):
            if len(current) > 0:
                sections.append(current)
            current = [ line ]
        else:
            current.append(line)
    if len(current) > 0:
        sections.append(current)
    return sections

def get_multichar_symbols(sections):
    for section in sections:
        if len(section) > 0 and section[0] == 'Multichar_Symbols':
            return section[1:]
    return []

def get_lexicons(sections):
    lexicons = dict()
    for section in sections:
        if len(section) > 0 and section[0].startswith('LEXICON'):
            x = len('LEXICON ')
            name = section[0][x:].strip()
            lexicons[name] = list(map(lambda x: x.strip(), re.split('(?<!(?<!%)%);', ''.join(section[1:]))))
    return lexicons

def tokenize_rule(rule):            
    return re.split('(?<!(?<!%)%)\\s+', rule)

def parse_rules(lexicon):
    return list(map(lambda x: list(map(lambda y: y.strip(), x)),
        filter(
            lambda x: x != [''], 
            map(
                tokenize_rule, 
                lexicon))))

def parse_replacement(replacement):
    return list(map(lambda x: '' if x =='0' else x, re.split('(?<!(?<!%)%)\\:', replacement)))

def get_lexicons_rules(lexicons):
    lexicons_rules = dict()
    for tag in list(lexicons):
        lexicons_rules[tag] = parse_rules(lexicons[tag])
    return lexicons_rules

def read_lexc(lexc_filename):
    with open(lexc_filename) as lexc_file:
        lexc = lexc_file.read()
        lexc_lines = lexc.splitlines()
        no_comments = map(remove_comment_from_line, lexc_lines)
        no_blank_lines = filter(filter_blank_lines, no_comments)
        no_trailing_whitespace = map(lambda s: s.strip(), no_blank_lines)
        sections = separate_symbols_lexicon(no_trailing_whitespace)
        
        multichar_symbols = get_multichar_symbols(sections)
        lexicons = get_lexicons(sections)
        lexicons_rules = get_lexicons_rules(lexicons)
        
        return (multichar_symbols, lexicons_rules)

def trim_unconnected_rules(lexicons_rules, root):
    marked_tags = set()
    def trim_helper(current_tag):
        marked_tags.add(current_tag)
        rules = lexicons_rules[current_tag]
        for rule in rules:
            if rule[-1] not in marked_tags and rule[-1] != '#':
                trim_helper(rule[-1])
    trim_helper(root)

    new_lexicons_rules = dict(lexicons_rules)
    for tag in set(list(lexicons_rules)).difference(marked_tags):
        del new_lexicons_rules[tag]

    return new_lexicons_rules

def create_highlighted_lexicon_dep_graph(lexicons_rules, annotated_highlights, output_filename):
    dot = graphviz.Digraph(format='pdf')
    existing_edges = dict()

    highlights = list(map(lambda x: list(map(lambda y: y[2], x)), annotated_highlights))

    dot.attr('node', shape='box')
    for lexicon_tag in list(lexicons_rules):
        suffix = ''
        for highlight in annotated_highlights:
            for l, r, tag in highlight:
                if tag == lexicon_tag:
                    dot.attr('node', color='red', style='filled')
                    suffix = '\n' + l + ':' + r if l != '' or r != '' else ''
                    break
        suffix = suffix.replace('%<', '<').replace('%>', '>')
        dot.node(lexicon_tag, lexicon_tag + suffix)
        dot.attr('node', color='black', fontcolor='black', style='')

    for lexicon_tag in list(lexicons_rules):
        rules = lexicons_rules[lexicon_tag]
        for rule in rules:
            if rule[-1] != '#':
                if not lexicon_tag in existing_edges:
                    existing_edges[lexicon_tag] = []
                if rule[-1] not in existing_edges[lexicon_tag]:
                    for highlight in highlights:
                        if lexicon_tag in highlight and rule[-1] in highlight:
                            dot.attr('edge', color='red', arrowsize='2.0')
                    dot.edge(lexicon_tag, rule[-1])
                    existing_edges[lexicon_tag].append(rule[-1])
                    dot.attr('edge', color='black', arrowsize='1.0')

    dot.render(output_filename, view=False, cleanup=True)

def escape_form(form):
    return form.replace('<', '%<').replace('>', '%>')

def trace_analysis(lexicons_rules, root, left, right):
    def helper(path, left_current, right_current):
        paths = []
        rules = lexicons_rules[path[-1][2]]
        for rule in rules:
            if len(rule) == 1:
                if rule[-1] == '#':
                    if left_current == left and right_current == right:
                        paths.append(path)
                else:
                    paths.extend(
                        helper(path + [('', '', rule[-1])], 
                               left_current, 
                               right_current))
            elif len(rule) == 2:
                replacements = parse_replacement(rule[0])
                
                # TODO hacky workaround, replace
                if len(replacements) != 2:
                    continue
                    
                (left_new, right_new) = replacements
                left_combined = left_current + left_new
                right_combined = right_current + right_new
                
                if rule[-1] == '#':
                    if left_combined == left and right_combined == right:
                        paths.append(left_new, right_new, path)
                elif left.startswith(left_combined) and right.startswith(right_combined):
                    paths.extend(
                        helper(
                            path + [(left_new, right_new, rule[-1])], 
                            left_combined, 
                            right_combined))
        return paths
    return helper([('', '', root)], '', '')

def main():
    parser = argparse.ArgumentParser(description='Generate a trace graph of a word and its analysis from a lexc file.')
    parser.add_argument('lexc', help='lexc filename')
    parser.add_argument('output', help='output filename')
    parser.add_argument('lform', help='the stem of the word and its analyses')
    parser.add_argument('rform', help='the generated form of the stem')
    parser.add_argument('-r', '--root', help='root node to display')

    args = parser.parse_args()

    lform = escape_form(args.lform)
    rform = escape_form(args.rform)
    root = args.root if args.root is not None else 'Root'

    multichar_symbols, lexicons_rules = read_lexc(args.lexc)
    trace = trace_analysis(lexicons_rules, 'Root', lform, rform)

    trimmed = trim_unconnected_rules(lexicons_rules, root)
    create_highlighted_lexicon_dep_graph(trimmed, trace, args.output)

    print('Successfully wrote graph to ' + args.output + '.pdf')

if __name__ == '__main__':
    main()
