#added by the fix
from functools import cmp_to_key

def parse_input():
    """
    Parses the input to extract the number of books n and their titles.
    Returns a tuple (n, book_titles) where n is the number of books and book_titles is a list of book titles.
    Calls nothing.
    """
    n, _ = map(int, input().split())
    book_titles = [input().strip() for _ in range(n)]
    return n, book_titles

def create_indexed_list(book_titles):
    """
    Creates a list of tuples, where each tuple contains a book title and its original index.
    Calls nothing.
    Returns a list of tuples [(index, title), ...].
    """
    return [(index + 1, title) for index, title in enumerate(book_titles)]

def compare_titles(title1, title2):
    """
    Custom comparator function that compares two book titles according to the combined ascending-descending order.
    Calls nothing.
    Returns a negative number if title1 should come before title2, a positive number if title1 should come after title2, or 0 if they are equal.
    """
    for i in range(len(title1)):
        if i % 2 == 0:  # Odd position (0-indexed)
            if title1[i] != title2[i]:
                return ord(title1[i]) - ord(title2[i])
        else:  # Even position (0-indexed)
            if title1[i] != title2[i]:
                return ord(title2[i]) - ord(title1[i])
    return 0

#originally generated
# def sort_books(indexed_books):
#     """
#     Sorts the indexed book titles using a built-in sorting function with the custom comparator function.
#     Calls compare_titles().
#     Returns the sorted list of indexed book titles.
#     """
#     return sorted(indexed_books, key=lambda book: book[1], cmp=compare_titles)

#fixed
def sort_books(indexed_books):
    """
    Sorts the indexed book titles using a built-in sorting function with the custom comparator function.
    Calls compare_titles().
    Returns the sorted list of indexed book titles.
    """
    return sorted(indexed_books, key=cmp_to_key(lambda book1, book2: compare_titles(book1[1], book2[1])))

def extract_indices(sorted_books):
    """
    Extracts and returns the original indices of the book titles from the sorted list of tuples.
    Calls nothing.
    Returns a list of indices.
    """
    return [index for index, _ in sorted_books]

def main():
    """
    Main execution flow of the program.
    Calls parse_input(), create_indexed_list(), sort_books(), and extract_indices().
    """
    n, book_titles = parse_input()
    indexed_books = create_indexed_list(book_titles)
    sorted_books = sort_books(indexed_books)
    sorted_indices = extract_indices(sorted_books)
    print(' '.join(map(str, sorted_indices)))

if __name__ == "__main__":
    main()